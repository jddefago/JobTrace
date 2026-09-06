"""Shared Gmail message-body extraction, used by both fetchers
(sync/agent.py's ApiFetcher and sync/imap.py's ImapFetcher) so the two
paths hand the classifier byte-for-byte identical text.
"""

import re

# Cap on the plain-text body handed to the classifier: enough for any real
# recruiter email, short enough to keep token cost predictable.
MAX_BODY_CHARS = 20000


def extract_body_text(msg):
    """Best plain-text rendering of an ``email.message.EmailMessage``,
    truncated to MAX_BODY_CHARS. HTML-only parts are stripped to text."""
    body_part = msg.get_body(preferencelist=("plain", "html"))
    if body_part is None:
        return ""
    content = body_part.get_content()
    if body_part.get_content_type() == "text/html":
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()
    return content[:MAX_BODY_CHARS]
