import logging

import pytest

from backend.admin.security import mailer
from backend.admin.security.mailer import AdminMailer, FakeTransport, MailConfig


def make(fail=False):
    transport = FakeTransport(fail=fail)
    return AdminMailer.for_transport(transport), transport


async def test_sign_in_code_mail():
    admin_mailer, transport = make()
    assert await admin_mailer.send_sign_in_code(
        "ann@example.org", "12345678", "203.0.113.9"
    )
    (message,) = transport.sent
    assert transport.recipients == ["ann@example.org"]
    assert message.subject == mailer.SUBJECT_SIGN_IN_CODE
    assert "12345678" in message.body and "203.0.113.9" in message.body
    assert "Not you? Ignore this message" in message.body
    assert "12345678" not in message.subject


async def test_notices_go_to_every_admin():
    admin_mailer, transport = make()
    admins = ["a@example.org", "b@example.org", "c@example.org"]
    assert (
        await admin_mailer.notify_enrolment(admins, "a@example.org", "203.0.113.9") == 3
    )
    assert (
        await admin_mailer.notify_recovery_use(
            admins, "a@example.org", "203.0.113.9", 7
        )
        == 3
    )
    assert (
        await admin_mailer.notify_lockout(admins, "a@example.org", "203.0.113.9", 15)
        == 3
    )
    assert transport.recipients[:3] == admins
    subjects = {m.subject for m in transport.sent}
    assert subjects == {
        mailer.SUBJECT_ENROLMENT,
        mailer.SUBJECT_RECOVERY_USE,
        mailer.SUBJECT_LOCKOUT,
    }
    recovery_body = transport.sent[3].body
    assert "Recovery codes left: 7" in recovery_body


def test_subjects_are_constants_free_of_user_text():
    for message in (
        mailer.sign_in_code_message("1", "x\r\nBcc: evil@example.org"),
        mailer.enrolment_message("evil\r\nBcc: x", "1.1.1.1"),
        mailer.recovery_use_message("a\nb", "1.1.1.1", 3),
        mailer.lockout_message("a\nb", "1.1.1.1", 15),
    ):
        assert "\n" not in message.subject and "evil" not in message.subject


def test_interpolated_values_are_one_plain_line():
    message = mailer.enrolment_message(
        "<b>x</b>\r\nBcc: evil@example.org & co", "1.1.1.1"
    )
    assert "<b>x</b> Bcc: evil@example.org & co" in message.body
    assert "\r" not in message.body.split("account ", 1)[1].split("\n", 1)[0]
    assert mailer.clean("a\x00b c") == "a b c"
    long = mailer.clean("x" * 1000)
    assert len(long) <= mailer.MAX_VALUE
    assert mailer.clean("\"'") == "\"'"


async def test_failures_are_swallowed_and_logged_without_recipient_or_code(caplog):
    admin_mailer, _ = make(fail=True)
    with caplog.at_level(logging.DEBUG):
        ok = await admin_mailer.send_sign_in_code(
            "secret.person@example.org", "87654321", "203.0.113.9"
        )
        sent = await admin_mailer.notify_lockout(
            ["x@example.org", "y@example.org"], "a@b.c", "1.1.1.1", 15
        )
    assert ok is False and sent == 0
    assert caplog.records
    text = caplog.text
    assert "secret.person" not in text and "87654321" not in text
    assert "x@example.org" not in text and "ConnectionError" in text


async def test_one_failing_recipient_does_not_stop_the_others():
    class Flaky(FakeTransport):
        async def send(self, to, subject, body):
            if to == "bad@example.org":
                raise OSError("boom")
            await super().send(to, subject, body)

    transport = Flaky()
    sent = await AdminMailer.for_transport(transport).notify_enrolment(
        ["a@example.org", "bad@example.org", "c@example.org"],
        "a@example.org",
        "1.1.1.1",
    )
    assert sent == 2 and transport.recipients == ["a@example.org", "c@example.org"]


def test_mail_config_from_env_uses_the_platform_names():
    cfg = MailConfig.from_env(
        {
            "MAIL_USER": "u",
            "MAIL_PASSWORD": "p",
            "MAIL_SMTP_SERVER": "smtp.example.org",
            "MAIL_SMTP_PORT": "2525",
            "MAIL_SENDER": "admin@example.org",
            "MAIL_STARTTLS": "false",
            "MAIL_VALIDATE_CERTS": "0",
            "MAIL_SSL_TLS": "yes",
        }
    )
    assert (cfg.user, cfg.smtp_server, cfg.smtp_port, cfg.sender) == (
        "u",
        "smtp.example.org",
        2525,
        "admin@example.org",
    )
    assert cfg.starttls is False and cfg.validate_certs is False and cfg.ssl_tls is True
    assert cfg.use_credentials is True and cfg.configured
    empty = MailConfig.from_env({"MAIL_SMTP_PORT": "x"})
    assert empty.smtp_port == 587 and not empty.configured


async def test_fastmail_transport_builds_a_plain_text_message(monkeypatch):
    import fastapi_mail

    captured = {}

    async def fake_send(self, message, template_name=None):
        captured["message"] = message

    monkeypatch.setattr(fastapi_mail.FastMail, "send_message", fake_send)
    transport = mailer.FastMailTransport(
        MailConfig(smtp_server="smtp.example.org", sender="admin@example.org")
    )
    await transport.send("ann@example.org", "Subject", "Body")
    message = captured["message"]
    assert message.subject == "Subject" and message.body == "Body"
    assert message.subtype == fastapi_mail.MessageType.plain
    assert [r.email for r in message.recipients] == ["ann@example.org"]


@pytest.mark.parametrize("value", [None, 5, ["x"]])
def test_clean_accepts_any_object(value):
    assert isinstance(mailer.clean(value), str)


async def test_provider_is_consulted_on_every_send_and_transport_rebuilt_on_change():
    first, second = FakeTransport(), FakeTransport()
    built = []

    def factory(config):
        built.append(config.sender)
        return first if config.sender == "a@example.org" else second

    class Switch:
        config = MailConfig(smtp_server="smtp.example.org", sender="a@example.org")

        def get(self):
            return self.config

    provider = Switch()
    admin_mailer = AdminMailer(provider, factory)
    assert await admin_mailer.send_sign_in_code("x@example.org", "12345678", "1.1.1.1")
    assert await admin_mailer.send_sign_in_code("x@example.org", "12345678", "1.1.1.1")
    assert built == ["a@example.org"] and len(first.sent) == 2
    provider.config = MailConfig(smtp_server="smtp.example.org", sender="b@example.org")
    assert await admin_mailer.send_sign_in_code("x@example.org", "12345678", "1.1.1.1")
    assert built == ["a@example.org", "b@example.org"] and len(second.sent) == 1


async def test_unconfigured_or_failing_provider_is_a_logged_non_event(caplog):
    class Broken:
        def get(self):
            raise KeyError("secret-setting-name")

    for provider in (Broken(), mailer.StaticMailConfigProvider(MailConfig())):
        admin_mailer = AdminMailer(provider, lambda c: FakeTransport())
        assert (
            await admin_mailer.send_sign_in_code("x@example.org", "87654321", "1.1.1.1")
            is False
        )
    assert "87654321" not in caplog.text and "x@example.org" not in caplog.text


def test_env_provider_reads_the_environment_each_time():
    env = {"MAIL_SMTP_SERVER": "a", "MAIL_SENDER": "s@example.org"}
    provider = mailer.EnvMailConfigProvider(env)
    assert provider.get().smtp_server == "a"
    env["MAIL_SMTP_SERVER"] = "b"
    assert provider.get().smtp_server == "b"
    assert isinstance(provider, mailer.MailConfigProvider)
