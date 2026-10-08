"""Fallback for when your Zoom admin (e.g. UT) won't let you create a webhook app.

Zoom can email you when participants join your meeting before you do
(Settings > Meeting > "Notify host when participants join the meeting before host").
This script watches a mailbox over IMAP for those emails and calls you.

Run:  python -m zoomnotifier.email_watcher
"""

import email
import imaplib
import logging
import os
import re
import time
from email.header import decode_header, make_header

from .config import Settings
from .notifier import Notifier

log = logging.getLogger(__name__)


def _header(msg, name: str) -> str:
    return str(make_header(decode_header(msg.get(name, ""))))


def is_zoom_join_email(sender: str, subject: str, subject_pattern: str) -> bool:
    return "zoom.us" in sender.lower() and re.search(subject_pattern, subject, re.I) is not None


def check_once(imap: imaplib.IMAP4, notifier: Notifier, subject_pattern: str) -> int:
    """Process unread Zoom emails. Returns how many matched."""
    imap.select("INBOX")
    status, data = imap.search(None, '(UNSEEN FROM "zoom.us")')
    if status != "OK":
        return 0
    matched = 0
    for num in data[0].split():
        # BODY.PEEK so non-matching mail stays unread.
        status, parts = imap.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        if status != "OK" or not parts or not isinstance(parts[0], tuple):
            continue
        msg = email.message_from_bytes(parts[0][1])
        sender, subject = _header(msg, "From"), _header(msg, "Subject")
        if not is_zoom_join_email(sender, subject, subject_pattern):
            continue
        matched += 1
        imap.store(num, "+FLAGS", "\\Seen")
        log.info("Zoom email: %s", subject)
        notifier.alert("email", "Someone")
    return matched


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    notifier = Notifier(settings)
    host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    user = os.environ["IMAP_USER"]
    password = os.environ["IMAP_PASSWORD"]
    interval = int(os.environ.get("POLL_SECONDS", "20"))
    pattern = os.environ.get("ZOOM_EMAIL_SUBJECT_PATTERN", r"join")

    while True:
        try:
            with imaplib.IMAP4_SSL(host) as imap:
                imap.login(user, password)
                log.info("Watching %s for Zoom join emails every %ss", user, interval)
                while True:
                    check_once(imap, notifier, pattern)
                    time.sleep(interval)
        except Exception:
            log.exception("IMAP error; reconnecting in 30s")
            time.sleep(30)


if __name__ == "__main__":
    main()
