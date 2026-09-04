"""Read-only Gmail access over IMAP with a Gmail *app password* — the
low-friction alternative to a Google Cloud OAuth client for the keys-based
sync (backend/sync/agent.py).

Setup for the user is two minutes: myaccount.google.com -> Security ->
2-Step Verification -> App passwords -> generate one for "Mail", paste it
(plus the Gmail address) into JobTrace's Sync settings. No Cloud console,
no consent screen, no OAuth client.

This exposes the same three operations the sync agent needs, matching
the API fetcher in agent.py:

    list_labels()                       -> [{"id","name"}, ...]
    search(query, include_trash=True)   -> [gmail_message_id_hex, ...]
    get_message(gmail_message_id_hex)   -> {id, threadId, labelIds, from,
                                            to, subject, date, body}

Gmail's IMAP `X-GM-RAW` extension accepts full Gmail search syntax
(`label:"..."`, `newer_than:30d`, `-label:...`, keywords), and `X-GM-MSGID`
is the same 64-bit id the Gmail API exposes as its hex `message.id` — so
message IDs, dedup, and the GMAIL_SYNC.md query logic all carry over
unchanged from the API path.
"""

import email
import email.policy
import imaplib
import re

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
MAX_BODY_CHARS = 20000


def _extract_body_text(msg):
    body_part = msg.get_body(preferencelist=("plain", "html"))
    if body_part is None:
        return ""
    content = body_part.get_content()
    if body_part.get_content_type() == "text/html":
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()
    return content[:MAX_BODY_CHARS]


def _hexid(x_gm_value):
    """X-GM-MSGID / X-GM-THRID come back as a decimal string; the Gmail API
    uses the lower-case hex of the same number as its id."""
    return format(int(x_gm_value), "x")


class ImapFetcher:
    def __init__(self, address, app_password):
        if not address or not app_password:
            raise ValueError("Gmail address and app password are both required for IMAP sync.")
        self._address = address
        self._password = app_password
        self._conn = None
        self._selected = None
        self._mailboxes = None
        self._locator = {}   # hex id -> (mailbox, uid)

    # -- connection -----------------------------------------------------
    def _c(self):
        if self._conn is None:
            self._conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=45)
            try:
                self._conn.login(self._address, self._password)
            except imaplib.IMAP4.error as e:
                raise RuntimeError(
                    "Gmail rejected the address / app password. It must be an "
                    "app password (myaccount.google.com -> Security -> App "
                    f"passwords), not your normal password. [{e}]"
                )
        return self._conn

    def account_email(self):
        return self._address

    def close(self):
        if self._conn is not None:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _select(self, mailbox):
        if self._selected != mailbox:
            typ, _ = self._c().select(f'"{mailbox}"', readonly=True)
            if typ != "OK":
                raise RuntimeError(f"Could not open mailbox {mailbox}")
            self._selected = mailbox

    # -- mailbox discovery -------------------------------------------
    def _special(self):
        """Resolve the All Mail / Trash / Spam folder names (locale-dependent)
        from their SPECIAL-USE flags."""
        if self._mailboxes is not None:
            return self._mailboxes
        wanted = {"\\All": None, "\\Trash": None, "\\Junk": None}
        typ, rows = self._c().list()
        if typ == "OK":
            for row in rows or []:
                line = row.decode() if isinstance(row, bytes) else row
                m = re.match(r'\((?P<flags>[^)]*)\)\s+"[^"]*"\s+(?P<name>.+)', line)
                if not m:
                    continue
                name = m.group("name").strip().strip('"')
                for flag in wanted:
                    if flag in m.group("flags"):
                        wanted[flag] = name
        self._mailboxes = {
            "all": wanted["\\All"] or "[Gmail]/All Mail",
            "trash": wanted["\\Trash"] or "[Gmail]/Trash",
            "spam": wanted["\\Junk"] or "[Gmail]/Spam",
        }
        return self._mailboxes

    # -- API expected by the sync agent -------------------------------
    def list_labels(self):
        typ, rows = self._c().list()
        out = []
        if typ == "OK":
            for row in rows or []:
                line = row.decode() if isinstance(row, bytes) else row
                m = re.match(r'\([^)]*\)\s+"[^"]*"\s+(?P<name>.+)', line)
                if not m:
                    continue
                raw = m.group("name").strip().strip('"')
                display = raw.split("/")[-1] if raw.startswith("[Gmail]/") else raw
                if raw.startswith("[Gmail]") and raw == "[Gmail]":
                    continue
                out.append({"id": raw, "name": display})
        return out

    def search(self, query, include_trash=True, max_results=300):
        mb = self._special()
        targets = [mb["all"]]
        if include_trash:
            targets += [mb["trash"], mb["spam"]]

        seen = []
        seen_set = set()
        for mailbox in targets:
            try:
                self._select(mailbox)
            except RuntimeError:
                continue
            typ, data = self._c().uid("search", None, "X-GM-RAW", f'"{query}"')
            if typ != "OK" or not data or not data[0]:
                continue
            uids = data[0].split()
            # newest first, and don't fetch msgids for more than we'll keep
            for uid in reversed(uids):
                if len(seen) >= max_results:
                    break
                typ, mdata = self._c().uid("fetch", uid, "(X-GM-MSGID)")
                if typ != "OK" or not mdata or not mdata[0]:
                    continue
                blob = mdata[0].decode() if isinstance(mdata[0], bytes) else str(mdata[0])
                m = re.search(r"X-GM-MSGID\s+(\d+)", blob)
                if not m:
                    continue
                hid = _hexid(m.group(1))
                if hid in seen_set:
                    continue
                seen_set.add(hid)
                self._locator[hid] = (mailbox, uid)
                seen.append(hid)
        return seen

    def _locate(self, message_id):
        if message_id in self._locator:
            return self._locator[message_id]
        # Not from this run's search — find it by its numeric Gmail id.
        decimal = str(int(message_id, 16))
        for mailbox in self._special().values():
            try:
                self._select(mailbox)
            except RuntimeError:
                continue
            typ, data = self._c().uid("search", None, "X-GM-MSGID", decimal)
            if typ == "OK" and data and data[0]:
                uid = data[0].split()[0]
                self._locator[message_id] = (mailbox, uid)
                return mailbox, uid
        raise RuntimeError(f"Message {message_id} not found in Gmail.")

    def get_message(self, message_id):
        mailbox, uid = self._locate(message_id)
        self._select(mailbox)
        typ, data = self._c().uid("fetch", uid, "(BODY.PEEK[] X-GM-THRID X-GM-LABELS)")
        if typ != "OK" or not data:
            raise RuntimeError(f"Could not fetch message {message_id}")

        raw_bytes, meta = b"", ""
        for part in data:
            if isinstance(part, tuple) and len(part) == 2:
                raw_bytes = part[1]
                meta += part[0].decode(errors="replace") if isinstance(part[0], bytes) else str(part[0])
            elif isinstance(part, (bytes, bytearray)):
                meta += part.decode(errors="replace")

        msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
        thr = re.search(r"X-GM-THRID\s+(\d+)", meta)
        labels = re.search(r"X-GM-LABELS\s+\(([^)]*)\)", meta)
        return {
            "id": message_id,
            "threadId": _hexid(thr.group(1)) if thr else None,
            "labelIds": [l.strip().strip('"') for l in (labels.group(1).split() if labels else [])],
            "from": msg.get("From", ""),
            "to": msg.get("To", ""),
            "subject": msg.get("Subject", ""),
            "date": msg.get("Date", ""),
            "body": _extract_body_text(msg),
        }
