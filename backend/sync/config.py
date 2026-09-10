"""Read/write data/sync_config.json — the user's Gmail-sync preferences and,
for the keys-based method, their secrets.

The file is gitignored (it lives under data/). The HTTP layer never returns
secret values: get_config_public() replaces them with a boolean "is it set".
"""

import copy
import json
import os
import threading

from .. import database

CONFIG_PATH = os.path.join(database.DATA_DIR, "sync_config.json")

# method -- also decides *when* sync runs:
#   "manual"  -- nothing automatic. You ask your AI assistant to sync (default).
#   "cli"     -- on dashboard load (once/day max), shell out to `claude`/`codex`.
#   "keys"    -- on dashboard load (once/day max), run in-process using a Gmail
#                app password (IMAP) or a Google OAuth token + your Anthropic key.
DEFAULTS = {
    "method": "manual",
    "cli": {
        "command": "claude",          # "claude" | "codex"
    },
    "keys": {
        "gmail_transport": "imap",     # "imap" (app password) | "api" (OAuth)
        "gmail_address": "",
        "gmail_app_password": "",       # secret
        "anthropic_api_key": "",        # secret
        "model": "claude-sonnet-5",
        "gmail_label": "Job Applications",
        "lookback_days": 30,
        # Lets the sync fill in location / job_url / source from the web
        # (GMAIL_SYNC.md's enrichment step). On by default; turn off in
        # Settings if you'd rather the model not have a web tool while it
        # reads email.
        "enable_web_search": True,
    },
}

SECRET_KEYS = (("keys", "gmail_app_password"), ("keys", "anthropic_api_key"))
_CLEAR = "__clear__"          # sentinel a PUT can send to blank a secret

_lock = threading.RLock()


def _deep_merge(base, over):
    """Merge `over` onto a deep copy of `base` — callers (and the module-level
    DEFAULTS) must never be mutated by what they get back. `over` is always a
    throwaway dict (freshly parsed JSON, or a transient UI patch), so its
    values can be adopted as-is."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _prune_to_shape(value, shape):
    """Keep only keys that exist in DEFAULTS, at every level — so a stray
    field from the UI (e.g. a `*_set` display flag) never lands in the file."""
    if isinstance(shape, dict) and isinstance(value, dict):
        return {k: _prune_to_shape(value[k], shape[k]) for k in shape if k in value}
    return value


def load():
    """Full config including secrets — for the runner / sync jobs only."""
    with _lock:
        stored = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    stored = json.load(f) or {}
            except (json.JSONDecodeError, OSError):
                stored = {}
        # Prune to DEFAULTS' shape so a stale section from an older version
        # (e.g. the removed "auto" timer block) never reaches callers.
        return _prune_to_shape(_deep_merge(DEFAULTS, stored), DEFAULTS)


def _write(cfg):
    database.ensure_data_dirs()
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)
    try:
        os.chmod(CONFIG_PATH, 0o600)   # it can hold an app password + API key
    except OSError:
        pass


def get_public():
    """Config safe to hand to the browser: secrets become `<key>_set: bool`."""
    cfg = load()
    for section, key in SECRET_KEYS:
        val = cfg.get(section, {}).pop(key, "")
        cfg[section][key + "_set"] = bool(val)
    return cfg


def update(patch):
    """Merge a patch from the UI. For secret fields: omit to leave unchanged,
    send "__clear__" to blank, send any other string to set."""
    with _lock:
        cfg = load()
        patch = dict(patch or {})

        # pull secrets out of the patch and apply their special rules
        patch_keys = patch.get("keys", {}) if isinstance(patch.get("keys"), dict) else {}
        for section, key in SECRET_KEYS:
            if key in patch_keys:
                incoming = patch_keys.pop(key)
                if incoming == _CLEAR:
                    cfg[section][key] = ""
                elif isinstance(incoming, str) and incoming.strip():
                    cfg[section][key] = incoming.strip()
                # empty / None -> leave as-is
        if "keys" in patch:
            patch["keys"] = patch_keys

        merged = _deep_merge(cfg, patch)

        # clamp / sanitise
        merged["method"] = merged["method"] if merged["method"] in ("manual", "cli", "keys") else "manual"
        merged["cli"]["command"] = merged["cli"].get("command") if merged["cli"].get("command") in ("claude", "codex") else "claude"
        kt = merged["keys"].get("gmail_transport")
        merged["keys"]["gmail_transport"] = kt if kt in ("imap", "api") else "imap"
        try:
            lb = int(merged["keys"].get("lookback_days", 30))
        except (TypeError, ValueError):
            lb = 30
        merged["keys"]["lookback_days"] = min(365, max(1, lb))

        _write(_prune_to_shape(merged, DEFAULTS))
        return get_public()
