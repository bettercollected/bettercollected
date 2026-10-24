import datetime as dt
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime

import pytest

from smoke.config import MAILPIT, MailboxSettings
from smoke.mail import CodeMailError, extract_code, newest_code_mail, parse_message
from smoke.mailbox import Mailbox, MailboxError, _quote_imap
from smoke.redact import Redactor

RUN = "smoke+smoke-123-1-abcdef@gmail.com"
OTHER_RUN = "smoke+smoke-999-1-000000@gmail.com"
SENT = dt.datetime(2026, 10, 24, 21, 0, tzinfo=dt.timezone.utc)


def mail(
    to: str, when: dt.datetime, code: str = "Q7X-4KD", body: str = None, **headers
) -> bytes:
    message = EmailMessage()
    message["From"] = "Example Forms <no-reply@example.com>"
    message["To"] = to
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
    message["Subject"] = "Your Example Forms verification code"
    message["Date"] = format_datetime(when)
    html = (
        body
        if body is not None
        else (
            '<p>Enter this code:</p><span style="letter-spacing:0.25em;">'
            f"{code}</span><p>It expires in 5 minutes.</p>"
        )
    )
    message.make_mixed()
    part = EmailMessage()
    part.set_content(html, subtype="html", cte="base64")
    message.attach(part)
    return message.as_bytes(policy=SMTP)


def test_the_fixture_mail_parses(code_mail_bytes):
    message = parse_message("1", code_mail_bytes)
    assert message.recipients == (RUN,)
    assert message.date == SENT
    assert extract_code(message) == "Q7X-4KD"


def test_quoted_printable_and_plain_text():
    message = EmailMessage()
    message["To"] = RUN
    message["Date"] = format_datetime(SENT)
    message.set_content(
        "Your code is AB1-C2D. It expires soon.", cte="quoted-printable"
    )
    assert extract_code(parse_message("1", message.as_bytes())) == "AB1-C2D"


def test_only_the_newest_mail_to_this_runs_address_counts():
    messages = [
        parse_message("1", mail(RUN, SENT + dt.timedelta(seconds=5), "OLD-111")),
        parse_message("2", mail(RUN, SENT + dt.timedelta(seconds=40), "NEW-222")),
        # newer, but to another run's address
        parse_message("3", mail(OTHER_RUN, SENT + dt.timedelta(seconds=60), "XXX-333")),
        # to this address, but from long before the code was asked for
        parse_message("4", mail(RUN, SENT - dt.timedelta(hours=2), "ANC-444")),
    ]
    newest = newest_code_mail(messages, RUN, SENT)
    assert newest.id == "2"
    assert extract_code(newest) == "NEW-222"


def test_a_little_clock_skew_is_allowed():
    messages = [parse_message("1", mail(RUN, SENT - dt.timedelta(seconds=30)))]
    assert newest_code_mail(messages, RUN, SENT).id == "1"


def test_the_base_address_or_another_tag_never_matches():
    for to in ("smoke@gmail.com", OTHER_RUN, "smoke+smoke-123-1-abcde@gmail.com"):
        assert newest_code_mail([parse_message("1", mail(to, SENT))], RUN, SENT) is None


def test_recipient_from_delivered_to_and_case():
    raw = mail("Undisclosed recipients:;", SENT, Delivered_To=RUN.upper())
    assert newest_code_mail([parse_message("1", raw)], RUN, SENT).id == "1"


@pytest.mark.parametrize(
    "body, problem",
    [
        ("<p>No code here, sorry.</p>", "no sign-in code"),
        ("<span>AAA-111</span> or <span>BBB-222</span>", "more than one"),
    ],
    ids=["none", "two"],
)
def test_no_or_ambiguous_code_is_refused_without_quoting_it(body, problem):
    with pytest.raises(CodeMailError) as error:
        extract_code(parse_message("1", mail(RUN, SENT, body=body)))
    assert problem in str(error.value)
    assert "AAA-111" not in str(error.value)


def test_the_same_code_twice_is_fine():
    body = "<span>ZZ9-9ZZ</span><p>Code ZZ9-9ZZ</p>"
    assert extract_code(parse_message("1", mail(RUN, SENT, body=body))) == "ZZ9-9ZZ"


class FakeMailbox(Mailbox):
    def __init__(self, batches):
        super().__init__(
            MailboxSettings(kind=MAILPIT, address="smoke@gmail.com"), Redactor()
        )
        self.batches = list(batches)
        self.fetches = 0

    def fetch(self, address, since):
        self.fetches += 1
        return self.batches.pop(0) if self.batches else []


def test_wait_for_code_polls_until_the_mail_arrives_and_registers_it():
    arrived = [
        parse_message("1", mail(RUN, SENT + dt.timedelta(seconds=20), "WAI-7ED"))
    ]
    box = FakeMailbox([[], [], arrived])
    naps = []
    code = box.wait_for_code(RUN, SENT, timeout=60, sleep=naps.append, clock=lambda: 0)
    assert code == "WAI-7ED"
    assert box.fetches == 3 and naps == [5, 5]
    assert "WAI-7ED" not in box.redactor.scrub("code WAI-7ED")


def test_wait_for_code_gives_up_without_a_storm():
    box = FakeMailbox([])
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    with pytest.raises(MailboxError, match="within 30 s"):
        box.wait_for_code(RUN, SENT, timeout=30, sleep=sleep, clock=lambda: now[0])
    # one look every 5 seconds, never faster
    assert box.fetches == 7


def test_mail_to_other_addresses_is_never_read():
    other = [parse_message("9", mail(OTHER_RUN, SENT + dt.timedelta(seconds=5)))]
    box = FakeMailbox([other])
    now = [0.0]
    with pytest.raises(MailboxError):
        box.wait_for_code(
            RUN,
            SENT,
            timeout=1,
            sleep=lambda s: now.__setitem__(0, now[0] + s),
            clock=lambda: now[0],
        )
    assert box.read_ids == set()


def test_imap_search_values_are_checked():
    assert _quote_imap(RUN) == f'"{RUN}"'
    for bad in ('a"b@gmail.com', "a b@gmail.com", "a\r\nb@gmail.com"):
        with pytest.raises(MailboxError):
            _quote_imap(bad)


def test_read_only_access_keeps_the_mail():
    box = FakeMailbox([])
    assert "left in the mailbox" in box.cleanup(RUN)
