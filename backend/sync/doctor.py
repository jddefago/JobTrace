"""Answer one question for the dashboard and for an AI assistant setting
JobTrace up: *can automatic Gmail sync actually run on this machine right
now, and if not, what's the one thing to fix?*

Every check is fast (a `which`, a short subprocess, an import) and never
touches the network except the optional IMAP login probe. Results are cached
briefly so the dashboard can poll cheaply.
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import time

from .. import database
from . import config as sync_config

# The server runs windowless (pythonw), but on Windows a child process
# spawned from it still gets its own console -- which flashes on screen and
# vanishes the instant the short-lived `mcp list` check exits. Suppress it.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

_CACHE = {"at": 0.0, "data": None}
_CACHE_TTL = 30.0

# Where the various installers drop the CLIs when they're not on PATH. People
# install these however they like -- native installer, Homebrew (Apple silicon
# and Intel differ), npm/pnpm/yarn global, nvm, or the older local install --
# so probe widely instead of assuming one layout. Entries may contain globs.
def _cli_candidates(name):
    return [
        f"~/.local/bin/{name}",                     # native installer
        f"~/.{name}/local/{name}",                  # legacy local install
        f"/opt/homebrew/bin/{name}",                # Homebrew, Apple silicon
        f"/usr/local/bin/{name}",                   # Homebrew, Intel
        f"~/.npm-global/bin/{name}",
        f"~/npm-global/bin/{name}",
        f"~/.nvm/versions/node/*/bin/{name}",       # nvm-managed node
        f"~/Library/pnpm/{name}",
        f"~/.yarn/bin/{name}",
        f"~/bin/{name}",
        os.path.join(os.environ.get("APPDATA", "~/AppData/Roaming"),
                     "npm", f"{name}.cmd"),         # Windows npm global
    ]


_CLI_PATHS = {
    "claude": _cli_candidates("claude"),
    "codex": _cli_candidates("codex"),
}


def _find_cli(name):
    """Locate a CLI: honour an explicit path, then PATH, then known install spots."""
    # The user may have configured an absolute path to a CLI we'd never guess.
    if os.path.sep in name or (os.path.altsep and os.path.altsep in name):
        expanded = os.path.expanduser(name)
        if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
            return expanded
        return None

    found = shutil.which(name)
    if found:
        return found
    for pattern in _CLI_PATHS.get(name, []):
        pattern = os.path.expanduser(pattern)
        matches = sorted(glob.glob(pattern)) if "*" in pattern else [pattern]
        for p in matches:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
    return None


def _claude_config_paths():
    """Every place a `claude` CLI might keep its top-level config, best first.

    Users install and relocate things differently: CLAUDE_CONFIG_DIR moves the
    whole config directory, and the file otherwise sits in the user's home. We
    probe rather than assume, and simply find nothing if none of them exist.
    """
    candidates = []
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        config_dir = os.path.expanduser(config_dir)
        candidates.append(os.path.join(config_dir, ".claude.json"))
        candidates.append(os.path.join(config_dir, "claude.json"))
    home = os.path.expanduser("~")
    candidates.append(os.path.join(home, ".claude.json"))
    candidates.append(os.path.join(home, ".config", "claude", ".claude.json"))
    candidates.append(os.path.join(home, ".claude", ".claude.json"))

    seen, out = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _claude_ai_connectors():
    """Names of the claude.ai connectors this machine's `claude` CLI has connected.

    These do NOT show up in `claude mcp list` — that command only knows about
    locally-configured MCP servers. A claude.ai connector (the kind you add with
    `/mcp` inside an interactive session) is recorded in ~/.claude.json instead,
    so checking only `mcp list` reports "no Gmail" even when Gmail is connected.
    """
    for path in _claude_config_paths():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        names = data.get("claudeAiMcpEverConnected")
        if isinstance(names, list):
            return [str(n) for n in names]
    return []


def _cli_has_gmail(binary):
    """Does this CLI have a Gmail connector — local MCP server or claude.ai one?"""
    if any("gmail" in name.lower() for name in _claude_ai_connectors()):
        return True
    try:
        out = subprocess.run(
            [binary, "mcp", "list"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=20,
            creationflags=_NO_WINDOW,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    blob = (out.stdout or "") + (out.stderr or "")
    return "gmail" in blob.lower()


def _check_cli(name):
    binary = _find_cli(name)
    if not binary:
        return {
            "name": name, "found": False, "ready": False,
            "fix": f"Install the {name} CLI, or make sure it's on your PATH.",
        }
    gmail = _cli_has_gmail(binary)
    ready = gmail is True
    fixes = []
    if gmail is False:
        fixes.append(
            f"Connect Gmail to the {name} CLI itself (this is separate from the "
            f"desktop app): run `{name}` in a terminal, then `/mcp` inside it, and "
            f"connect the claude.ai Gmail connector."
        )
    elif gmail is None:
        fixes.append(f"Couldn't query `{name} mcp list` — run it once in a terminal and sign in.")
    return {
        "name": name, "found": True, "path": binary,
        "gmail_connector": gmail, "ready": ready,
        "fix": " ".join(fixes) if fixes else None,
        "note": "Sign-in is verified on the first real run — an expired login shows up there.",
    }


def _check_keys():
    cfg = sync_config.load()["keys"]
    transport = cfg.get("gmail_transport", "imap")

    anthropic_ok = False
    try:
        import anthropic  # noqa: F401
        anthropic_ok = True
    except ImportError:
        pass

    google_ok = False
    if transport == "api":
        try:
            import googleapiclient  # noqa: F401
            import google_auth_oauthlib  # noqa: F401
            google_ok = True
        except ImportError:
            pass

    has_key = bool(cfg.get("anthropic_api_key"))
    if transport == "imap":
        gmail_configured = bool(cfg.get("gmail_address") and cfg.get("gmail_app_password"))
        gmail_deps_ok = True
    else:
        token_path = os.path.join(database.DATA_DIR, "gmail_api_token.json")
        gmail_configured = os.path.exists(token_path)
        gmail_deps_ok = google_ok

    fixes = []
    if not anthropic_ok:
        fixes.append("Install the Anthropic library: pip install -r requirements.txt")
    if not has_key:
        fixes.append("Add your Anthropic API key in Sync settings.")
    if transport == "imap" and not gmail_configured:
        fixes.append("Add your Gmail address and a Gmail app password in Sync settings "
                     "(myaccount.google.com → Security → App passwords).")
    if transport == "api" and not gmail_deps_ok:
        fixes.append("Install the Google API libraries: pip install google-api-python-client "
                     "google-auth-oauthlib")
    if transport == "api" and not gmail_configured:
        fixes.append("Run the one-time Gmail OAuth consent (see SETUP.md).")

    ready = anthropic_ok and has_key and gmail_configured and gmail_deps_ok
    return {
        "transport": transport,
        "anthropic_library": anthropic_ok,
        "anthropic_api_key_set": has_key,
        "gmail_configured": gmail_configured,
        "gmail_deps_ok": gmail_deps_ok,
        "ready": ready,
        "fixes": fixes,
    }


def check_imap_login():
    """Optional deeper probe: actually try to log in over IMAP. Not part of
    the cached report — called explicitly from a 'test connection' button."""
    cfg = sync_config.load()["keys"]
    addr, pw = cfg.get("gmail_address"), cfg.get("gmail_app_password")
    if not addr or not pw:
        return {"ok": False, "error": "No Gmail address / app password set."}
    import imaplib
    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=20)
        try:
            M.login(addr, pw)
            M.logout()
        finally:
            try:
                M.shutdown()
            except Exception:
                pass
        return {"ok": True}
    except imaplib.IMAP4.error as e:
        msg = str(e)
        if "Invalid credentials" in msg or "AUTHENTICATIONFAILED" in msg:
            return {"ok": False, "error": "Gmail rejected the address / app password. "
                    "Make sure it's an app password, not your normal password."}
        return {"ok": False, "error": msg}
    except OSError as e:
        return {"ok": False, "error": f"Could not reach imap.gmail.com: {e}"}


def invalidate():
    """Drop the cache so the next report() recomputes — cheap, runs no
    subprocess (unlike report(force=True))."""
    _CACHE["at"] = 0.0


def report(force=False):
    now = time.time()
    if not force and _CACHE["data"] is not None and now - _CACHE["at"] < _CACHE_TTL:
        return _CACHE["data"]

    cfg = sync_config.load()
    data = {
        "method": cfg["method"],
        "auto_enabled": cfg["method"] != "manual",
        "cli": {name: _check_cli(name) for name in ("claude", "codex")},
        "keys": _check_keys(),
    }
    # A single top-line answer the UI and an assistant can branch on.
    if cfg["method"] == "manual":
        data["ready"] = None
        data["headline"] = "Manual sync — ask your AI assistant to sync; nothing to configure here."
    elif cfg["method"] == "cli":
        chosen = data["cli"].get(cfg["cli"]["command"], {})
        data["ready"] = bool(chosen.get("ready"))
        data["headline"] = ("Ready — sync runs via the "
                            f"{cfg['cli']['command']} CLI when you open JobTrace." if data["ready"]
                            else chosen.get("fix") or "The CLI isn't ready yet.")
    else:
        data["ready"] = data["keys"]["ready"]
        data["headline"] = ("Ready — sync runs with your own keys when you open JobTrace."
                            if data["ready"] else (data["keys"]["fixes"][:1] or [""])[0])

    _CACHE.update(at=now, data=data)
    return data
