"""backend/sync/_gmail_text.py — shared message-body extraction used by both
the IMAP and API Gmail fetchers."""

import email
import email.policy
import unittest

from backend.sync import _gmail_text


def _msg(body, subtype="plain"):
    raw = (
        f"From: r@example.com\r\nTo: me@example.com\r\nSubject: hi\r\n"
        f"Content-Type: text/{subtype}; charset=utf-8\r\n\r\n{body}"
    ).encode("utf-8")
    return email.message_from_bytes(raw, policy=email.policy.default)


class ExtractBodyTextTests(unittest.TestCase):
    def test_plain_text_is_returned_as_is(self):
        self.assertEqual("Hello there", _gmail_text.extract_body_text(_msg("Hello there")))

    def test_html_is_stripped_to_text_and_whitespace_collapsed(self):
        out = _gmail_text.extract_body_text(_msg("<p>Hi   <b>Sam</b></p>\n<div>bye</div>", "html"))
        self.assertEqual("Hi Sam bye", out)

    def test_body_is_truncated_to_the_cap(self):
        out = _gmail_text.extract_body_text(_msg("x" * (_gmail_text.MAX_BODY_CHARS + 500)))
        self.assertEqual(_gmail_text.MAX_BODY_CHARS, len(out))


if __name__ == "__main__":
    unittest.main()
