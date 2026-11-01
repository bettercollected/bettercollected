"""The words of an email action: placeholders, escaping and the injection
matrix. Nothing a respondent types may become markup, a header line, another
placeholder or another recipient."""

import email
import time
from email import policy

import pytest

from backend.app.services.email_actions import templates, transport
from backend.app.services.email_actions.transport import MailFailed

ENTRIES = [
    ("name", "Full name", "Ada"),
    ("story", "Story", "Line one\nLine two"),
]
KW = dict(form_title="Intake", submitted_at="2026-10-31 09:00 UTC", language="en")


def body(template, entries=ENTRIES, **kw):
    return templates.render(template, entries, subject=False, **{**KW, **kw})


def subject(template, entries=ENTRIES, **kw):
    return templates.render(template, entries, subject=True, **{**KW, **kw})


def test_placeholders_are_filled_in_one_pass():
    assert body("Hello {{name}} / {{ form_title }}") == "Hello Ada / Intake"
    assert subject("{{name}} on {{submitted_at}}") == "Ada on 2026-10-31 09:00 UTC"


def test_the_answers_block_has_one_line_per_question_and_indents_long_answers():
    assert body("{{answers}}") == "Full name: Ada\nStory: Line one\n  Line two"


@pytest.mark.parametrize(
    "value",
    ["{{form_title}}", "{{answers}}", "{{ name }}", "{{ story }}", "{{{{name}}}}", "}}{{"],
)
def test_an_answer_that_looks_like_a_placeholder_stays_text(value):
    entries = [("name", "Full name", value), ("story", "Story", "S")]
    assert body("{{name}}", entries) == value
    assert value in body("{{answers}}", entries)
    assert subject("{{name}}", entries) == value


def test_html_in_an_answer_is_plain_text_never_markup():
    value = '<script>alert(1)</script><img src=x onerror=y> &amp; <a href="http://e.example">x</a>'
    entries = [("name", "Full name", value)]
    assert body("{{name}}", entries) == value  # no escaping, no tags added: it is plain text
    assert "<" not in body("no answers here {{form_title}}", entries)


@pytest.mark.parametrize(
    "value",
    [
        "x\r\nBcc: attacker@evil.example",
        "x\nBcc: attacker@evil.example",
        "x\rBcc: attacker@evil.example",
        "x Bcc: attacker@evil.example",
        "x Bcc: attacker@evil.example",
        "x\u0085Bcc: attacker@evil.example",
        "x\x0bBcc: attacker@evil.example",
        "x\x0cBcc: attacker@evil.example",
        "x\x00\x1b[31mBcc: attacker@evil.example",
    ],
)
def test_no_line_break_survives_in_the_subject(value):
    entries = [("name", "Full name", value)]
    line = subject("Re: {{name}}", entries)
    assert all(ch not in line for ch in "\r\n\x0b\x0c  \u0085\x00\x1b")
    # and the standard library agrees: it builds a one-header message
    message = transport.build_message(
        sender="noreply@example.test",
        sender_name="Acme",
        recipients=["owner@acme.example"],
        subject=line,
        body="b",
    )
    parsed = email.message_from_bytes(message.as_bytes(), policy=policy.default)
    assert parsed["Bcc"] is None
    assert parsed["To"] == "owner@acme.example"


def test_a_template_written_with_line_breaks_in_the_subject_is_one_line():
    assert subject("one\r\ntwo\nthree") == "one two three"


def test_the_standard_library_refuses_a_header_value_with_a_line_break():
    with pytest.raises(ValueError):
        transport.build_message(
            sender="noreply@example.test",
            sender_name="Acme",
            recipients=["owner@acme.example"],
            subject="a\r\nBcc: x@y.example",
            body="b",
        )
    with pytest.raises(ValueError):
        transport.build_message(
            sender="noreply@example.test",
            sender_name="Acme",
            recipients=["owner@acme.example\r\nBcc: x@y.example"],
            subject="a",
            body="b",
        )
    assert isinstance(transport.failure_of(ValueError("x")), MailFailed)
    assert transport.failure_of(ValueError("x")).permanent


def test_bidirectional_overrides_and_zero_width_characters_are_dropped():
    value = "evil‮gpj.exe​⁦x⁩﻿"
    assert templates.one_line(value, 100) == "evilgpj.exex"
    assert templates.clean("a‍b", multiline=False) == "a‍b"  # ZWJ of emoji sequences stays


def test_values_are_capped_and_the_whole_message_is_too():
    entries = [("name", "Full name", "a" * 5000)]
    assert len(body("{{name}}", entries)) == templates.VALUE_MAX
    assert len(subject("{{name}}", entries)) == templates.SUBJECT_VALUE_MAX
    huge = "x" * 9000
    many = [(f"k{i}", f"Q{i}", "v" * 1500) for i in range(40)]
    assert len(body(huge + "{{answers}}", many)) <= templates.MESSAGE_MAX


def test_a_question_the_form_no_longer_has_is_empty():
    assert body("[{{gone}}]") == "[]"


@pytest.mark.parametrize(
    "text,allowed,code",
    [
        ("{{name}} {{form_title}}", {"name", "form_title"}, None),
        ("{{ name }}", {"name"}, None),
        ("{{other}}", {"name"}, "unknown_placeholder"),
        ("{{name|upper}}", {"name"}, "invalid_placeholder"),
        ("{{ name", {"name"}, "invalid_placeholder"),
        ("name }}", {"name"}, "invalid_placeholder"),
        ("{{1abc}}", {"name"}, "invalid_placeholder"),
        ("{% if x %}", {"name"}, None),  # not our syntax: plain text
        ("${name}", {"name"}, None),
    ],
)
def test_placeholder_problems_are_found_at_save(text, allowed, code):
    problem = templates.placeholder_problem(text, allowed)
    assert (problem[0] if problem else None) == code


def test_values_are_formatted_by_kind_and_language():
    assert templates.format_value(True, "nl") == "Ja"
    assert templates.format_value(False, "en") == "No"
    assert templates.format_value(["Red", "Blue"]) == "Red, Blue"
    assert templates.format_value([{"a": "Bo", "b": 3}, {"a": "Cy"}]) == "1. Bo / 3\n2. Cy"
    assert templates.format_value(None) == ""


def test_the_newer_answers_read_as_text():
    # a currency as the export writes it, a range as an ISO 8601 interval, tags as a list
    assert templates.format_value({"code": "EUR", "amount": "12.50"}) == "EUR 12.50"
    assert templates.format_value({"code": None, "amount": "12.50"}) == "12.50"
    assert templates.format_value({"code": "EUR", "amount": None}) == "EUR"
    assert templates.format_value({"start": "2026-01-31", "end": "2026-02-03"}) == "2026-01-31/2026-02-03"
    assert templates.format_value({"start": "2026-01-31", "end": None}) == "2026-01-31/"
    assert templates.format_value(["alpha", "beta"]) == "alpha, beta"
    # an item of a repeating group is never read as a currency or a range, whatever
    # its questions are called, while the answers inside it are
    assert templates.format_value([{"code": "A", "amount": "1"}]) == "1. A / 1"
    assert templates.format_value(
        [{"stay": {"start": "2026-01-01", "end": "2026-01-02"}, "cost": {"code": "EUR", "amount": "3"}}]
    ) == "1. 2026-01-01/2026-01-02 / EUR 3"


def test_the_form_language_picks_the_template():
    class Settings:
        language = "nl-BE"

    class Form:
        settings = Settings()

    assert templates.language_of(Form()) == "nl"
    Settings.language = "de"
    assert templates.language_of(Form()) == "en"
    assert templates.language_of(None) == "en"
    assert templates.language_of({"settings": {"language": "NL"}}) == "nl"


def test_the_respondents_copy_is_fixed_wording_and_the_answers_with_no_form_title():
    entries = [("name", "Full name", "Ada")]
    for lang, word in (("en", "copy of your submission"), ("nl", "kopie van uw inzending")):
        subject_line, text = templates.render_respondent(entries, submitted_at="now", language=lang)
        assert word in subject_line.lower() and word in text.lower()
        assert "\n" not in subject_line and "Full name: Ada" in text
        assert '"' not in text.split("\n")[0]  # the intro names no form
    # nothing about the form reaches the copy, whatever the title is: render_respondent takes none
    import inspect

    assert "form_title" not in inspect.signature(templates.render_respondent).parameters


def test_a_multi_line_value_in_the_team_template_is_indented_so_it_cannot_forge_lines():
    entries = [("story", "Story", "first\nTotal: 0\nBcc: x@y.example")]
    text = body("Story:\n{{story}}\nEnd", entries)
    assert text == "Story:\nfirst\n  Total: 0\n  Bcc: x@y.example\nEnd"
    # one-line values are untouched, and the subject stays one line
    assert body("{{name}}") == "Ada"
    assert "\n" not in subject("{{story}}", entries)


@pytest.mark.parametrize(
    "variants,expected",
    [
        (["A.B+x@GMAIL.com", "ab@gmail.com", "a.b@googlemail.com", "AB+news+more@Gmail.Com", "a.b@gmail.com."], "ab@gmail.com"),
        (["victim+1@acme.example", "victim+2@ACME.example", "Victim@acme.example", "victim@acme.example."], "victim@acme.example"),
        (["jan@bücher.example", "jan@xn--bcher-kva.example", "JAN+x@BÜCHER.example", "jan@xn--bcher-kva.example."], "jan@xn--bcher-kva.example"),
        # dots are only dropped for Gmail
        (["a.b@acme.example"], "a.b@acme.example"),
    ],
)
def test_rate_limit_keys_treat_the_variants_of_one_mailbox_as_one(variants, expected):
    from backend.app.services.copy_recipient import rate_limit_key

    assert {rate_limit_key(v) for v in variants} == {expected}
    assert rate_limit_key("a.b@acme.example") != rate_limit_key("ab@acme.example")
    assert rate_limit_key("not an address") is None and rate_limit_key("a+b") is None
def test_the_message_is_plain_text_from_the_instance_with_an_auto_submitted_header():
    message = transport.build_message(
        sender="noreply@example.test",
        sender_name="Acme",
        recipients=["a@acme.example", "b@acme.example"],
        subject="Hello",
        body="Text <b>not bold</b>",
    )
    assert message.get_content_type() == "text/plain" and not message.is_multipart()
    assert message["Auto-Submitted"] == "auto-generated"
    assert message["From"] == "Acme <noreply@example.test>"
    assert message["To"] == "a@acme.example, b@acme.example"
    assert message["Cc"] is None and message["Bcc"] is None and message["Reply-To"] is None


@pytest.mark.parametrize(
    "error,code,permanent",
    [
        (TimeoutError(), "timeout", False),
        (ConnectionRefusedError(), "smtp_unavailable", False),
        (RuntimeError("x"), "smtp_error", False),
    ],
)
def test_failures_become_our_codes(error, code, permanent):
    failed = transport.failure_of(error)
    assert (failed.code, failed.permanent) == (code, permanent)


def test_smtp_errors_are_mapped_without_their_text():
    import aiosmtplib

    assert transport.failure_of(aiosmtplib.SMTPRecipientsRefused([])).permanent
    assert transport.failure_of(aiosmtplib.SMTPResponseException(550, "no such user")).code == "smtp_rejected"
    assert transport.failure_of(aiosmtplib.SMTPResponseException(451, "busy")).permanent is False
    assert transport.failure_of(aiosmtplib.SMTPAuthenticationError(535, "bad")).code == "smtp_auth"


BIDI = [chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A), 0x200E, 0x200F, 0x061C)]
SEPARATORS = ["\u2028", "\u2029", "\u0085"]


@pytest.mark.parametrize("mark", BIDI)
def test_every_bidirectional_override_and_isolate_is_stripped_from_values_and_names(mark):
    value = f"a{mark}b"
    entries = [("name", f"Q{mark}uestion", value)]
    assert subject("{{name}}", entries) == "ab"
    assert body("{{answers}}", entries) == "Question: ab"
    assert templates.one_line(f"Org{mark}name", 100) == "Orgname"  # display names (From)
    assert templates.clean(f"x{mark}y", multiline=True) == "xy"


@pytest.mark.parametrize("sep", SEPARATORS)
def test_line_and_paragraph_separators_and_nel_collapse_to_a_space_in_one_line_values(sep):
    entries = [("name", "Full name", f"a{sep}Bcc: x@y.example")]
    assert subject("{{name}}", entries) == "a Bcc: x@y.example"
    assert templates.one_line(f"Org{sep}name", 100) == "Org name"
    # in the body they are line breaks, never kept as separators
    assert sep not in body("{{name}}", entries)


@pytest.mark.parametrize("mark", BIDI + SEPARATORS + ["\r", "\n", "\t", " ", "\x00", "\u200b"])
def test_an_address_with_any_of_them_is_not_an_address(mark):
    from backend.app.services.copy_recipient import normalize_address

    assert normalize_address(f"ada{mark}@example.test") is None
    assert normalize_address(f"ada@exa{mark}mple.test") is None
    assert normalize_address("ada@example.test") == "ada@example.test"


# ----------------------------------------------- the respondent's copy: size and links


@pytest.mark.parametrize(
    "text,expected",
    [
        ("see https://evil.example/login now", "see [link removed] now"),
        ("HTTP://EVIL.example", "[link removed]"),
        ("ftp://a.example/x", "[link removed]"),
        ("www.evil.example/pay", "[link removed]"),
        ("evil.example", "[link removed]"),
        ("evil.example/pay?x=1#y", "[link removed]"),
        ("sub.evil.co.uk/x", "[link removed]"),
        ("mailto:victim@evil.example", "[link removed]"),
        ("javascript:alert(1)", "[link removed]"),
        ("go to evil.example, then www.evil.example.", "go to [link removed], then [link removed]"),
        ("a https://x.example b https://y.example c", "a [link removed] b [link removed] c"),
        # not links: plain words, numbers, and an email address (the respondent's own)
        ("Just words, and 3.14 and e.g. things", "Just words, and 3.14 and e.g. things"),
        ("ada@example.test", "ada@example.test"),
        ("write to ada@example.test please", "write to ada@example.test please"),
    ],
)
def test_links_are_removed_from_the_respondents_copy(text, expected):
    assert templates.defang_links(text) == expected


def _copy(entries):
    return templates.render_respondent(entries, submitted_at="now", language="en")[1]


def test_the_copy_removes_links_from_labels_and_answers_but_the_team_mail_keeps_them():
    entries = [("q", "Visit https://evil.example/now", "Pay at www.evil.example/pay or evil.example/x")]
    text = _copy(entries)
    assert "evil" not in text.lower() and text.count("[link removed]") == 3
    assert "Question" not in text
    team = body("{{answers}}", entries)
    assert "https://evil.example/now" in team and "www.evil.example/pay" in team


@pytest.mark.parametrize("unit", ["a", "a.", "a-", "a@", "-"])
def test_removing_links_from_a_long_copy_is_quick(unit):
    # each label and answer is cut before links are looked for, so a copy of
    # many long answers that look almost like links costs little to build
    long = unit * 1000
    entries = [(f"k{i}", long[:200], long) for i in range(50)]
    started = time.perf_counter()
    templates.copy_answers_block(entries)
    assert time.perf_counter() - started < 0.5


def test_every_label_and_answer_of_the_copy_is_cut_to_200_characters_and_the_block_to_2000():
    long = "x" * 5000
    text = _copy([("q", long, long)])
    line = [l for l in text.split("\n") if l.startswith("x")][0]
    label, _, answer = line.partition(": ")
    assert len(label) == 200 and label.endswith("…")
    assert len(answer) == 200 and answer.endswith("…")
    # the review's probe: 50 labels of 200 characters, answers of 2,000 with links
    entries = [(f"k{i}", ("L" * 190) + f" {i} https://evil.example/{i}", ("A " * 1000) + " https://evil.example/pay") for i in range(50)]
    block = templates.copy_answers_block(entries)
    assert len(block) <= templates.COPY_ANSWERS_MAX == 2000 and block.endswith("…")
    body_text = _copy(entries)
    assert "evil.example" not in body_text
    fixed = len(templates.render_respondent([], submitted_at="now", language="en")[1])
    assert len(body_text) <= fixed + 2000 + 100
    # the team's mail is not cut this way
    assert len(body("{{answers}}", [(f"k{i}", "L" * 190, "A" * 1500) for i in range(5)])) > 2000


def test_a_multi_line_answer_in_the_copy_is_indented_and_cut():
    text = _copy([("q", "Q", "first\nsecond\n" + "z" * 400)])
    assert "Q: first\n  second\n  " in text


# ---------------------------------------------------------------- other limits


def test_a_literal_encoded_word_in_a_subject_is_neutralised():
    entries = [("name", "Full name", "=?utf-8?q?hi=0D=0ABcc:_v@x.com?=")]
    line = subject("Re: {{name}} =?UTF-8?B?aGk=?=", entries)
    assert "=?" not in line and "= ?utf-8?q?hi=0D=0ABcc:_v@x.com?=" in line
    assert templates.subject_line("=?x?q?y?=") == "= ?x?q?y?="


def test_unassigned_code_points_are_kept_in_messages_but_not_in_addresses():
    from backend.app.services.copy_recipient import normalize_address

    newer_emoji = "\U0001fae8"  # unassigned in an older Unicode release than the sender's
    assert templates.clean(f"a{newer_emoji}b", multiline=True) == f"a{newer_emoji}b"
    assert normalize_address(f"ada{newer_emoji}@example.test") is None


def test_the_source_has_no_raw_invisible_characters():
    import pathlib

    root = pathlib.Path(templates.__file__).parent
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not any(ch in text for ch in "\u2028\u2029\u200b\u200d\u202e\u2066\ufeff"), path.name


@pytest.mark.parametrize("char", list('<>(),;:"\\[]%'))
def test_every_forbidden_character_makes_an_address_not_one(char):
    from backend.app.services.copy_recipient import normalize_address

    assert normalize_address(f"a{char}b@example.test") is None
    assert normalize_address(f"ab@exa{char}mple.test") is None


def test_the_wire_form_of_an_address_is_ascii_or_refused_for_good():
    from backend.app.services.email_actions.transport import ascii_recipient

    assert ascii_recipient("Jan@B\u00fccher.example") == "Jan@xn--bcher-kva.example"
    assert ascii_recipient("jan@xn--bcher-kva.example.") == "jan@xn--bcher-kva.example"
    assert ascii_recipient("ada+tag@example.test") == "ada+tag@example.test"
    for bad in ("j\u00e4n@example.test", "\u5f20@example.test"):
        with pytest.raises(MailFailed) as refused:
            ascii_recipient(bad)
        assert refused.value.code == "address_not_supported" and refused.value.permanent


# ------------------------------------------- compatibility forms of links (NFKC)


@pytest.mark.parametrize(
    "text",
    [
        "evil\uff0eexample",  # fullwidth full stop
        "evil\u3002example/pay",  # ideographic full stop
        "evil\uff61example",  # halfwidth ideographic full stop
        "evil\ufe52example",  # small full stop
        "evil\u2024example",  # one dot leader
        "\uff57\uff57\uff57\uff0eevil\uff0eexample",  # fullwidth www.evil.example
        "\uff48\uff54\uff54\uff50\uff53\uff1a\uff0f\uff0fevil\uff0eexample",  # fullwidth https://evil.example
        "\uff4d\uff41\uff49\uff4c\uff54\uff4f\uff1avictim\uff20evil\uff0eexample",  # fullwidth mailto:
        "visit evil\u3002example\uff0fpay now",
    ],
)
def test_compatibility_forms_of_a_link_are_found_in_the_respondents_copy(text):
    block = templates.copy_answers_block([("q", "Q " + text, text)])
    assert "evil" not in block and "[link removed]" in block, block
    # the team's mail is plain text as typed: it is not rewritten
    assert text in body("{{answers}}", [("q", "Q", text)])


def test_normalising_does_not_hide_a_link_behind_the_cut_and_the_cut_is_applied_again():
    # cut first (a link cut in the middle is still a link), then normalise, then search
    straddling = "a" * 190 + " evil.example/pay"
    block = templates.copy_answers_block([("q", "Q", straddling)])
    assert "evil" not in block
    # NFKC can lengthen a text ("\u3300" is four characters): cut again afterwards
    wide = templates.copy_item("\u3300" * 300, multiline=False)
    assert len(wide) <= templates.COPY_ITEM_MAX and wide.endswith("\u2026")
    # plain text is normalised: fullwidth letters and digits become the plain ones
    assert templates.copy_item("\uff21\uff22\uff23 \uff11\uff12\uff13", multiline=False) == "ABC 123"
    # an email address is still left alone once normalised
    assert templates.copy_item("ada\uff20example.test", multiline=False) == "ada@example.test"
