"""The IMAP reader against a fake server: it searches for this run's address
only, reads without marking as read, and bins only the mails it searched."""

import datetime as dt

from smoke.config import IMAP, MailboxSettings
from smoke.mailbox import ImapMailbox
from smoke.redact import Redactor
from tests.test_mail import RUN, SENT, mail


class FakeImap:
    def __init__(self, messages):
        self.messages = messages  # uid -> raw
        self.calls = []

    def noop(self):
        return "OK", [b""]

    def list(self):
        return "OK", [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Trash) "/" "[Gmail]/Bin"',
        ]

    def uid(self, command, *args):
        self.calls.append((command,) + args)
        if command == "SEARCH":
            return "OK", [b" ".join(self.messages)]
        if command == "FETCH":
            uid = args[0]
            return "OK", [(b"1 (UID " + uid + b" BODY[] {n}", self.messages[uid]), b")"]
        if command == "MOVE":
            return "OK", [b""]
        return "NO", [b""]

    def logout(self):
        pass


def mailbox(fake):
    box = ImapMailbox(
        MailboxSettings(
            kind=IMAP,
            address="smoke@gmail.com",
            imap_host="imap.gmail.com",
            app_password="x" * 16,
        ),
        Redactor(),
    )
    box._imap = fake
    return box


def test_reads_the_runs_code_without_marking_it_read():
    fake = FakeImap({b"7": mail(RUN, SENT + dt.timedelta(seconds=10), "IMA-P01")})
    box = mailbox(fake)
    assert box.wait_for_code(RUN, SENT, timeout=1, sleep=lambda s: None) == "IMA-P01"
    search = next(c for c in fake.calls if c[0] == "SEARCH")
    assert search[2:4] == ("TO", f'"{RUN}"')
    fetch = next(c for c in fake.calls if c[0] == "FETCH")
    assert fetch[2] == "(BODY.PEEK[])"


def test_cleanup_bins_only_the_searched_mails():
    fake = FakeImap({b"7": mail(RUN, SENT), b"9": mail(RUN, SENT)})
    box = mailbox(fake)
    assert box.cleanup(RUN) == "deleted 2 mail(s) to the run's address"
    move = next(c for c in fake.calls if c[0] == "MOVE")
    assert move[1:] == ("7,9", '"[Gmail]/Bin"')
    assert not any(c[0] == "STORE" for c in fake.calls)
