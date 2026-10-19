"""The portal's layered mail settings: environment first, then the saved ones."""

from __future__ import annotations

from backend.admin.security.mailer import (
    AdminMailer,
    LayeredMailConfigProvider,
    MailConfig,
    Message,
    mail_config_from_settings,
)

SAVED = MailConfig(smtp_server="saved.example.org", sender="saved@example.org")


def test_nothing_configured():
    provider = LayeredMailConfigProvider({})
    assert provider.source() == "none" and not provider.get().configured


def test_saved_settings_are_used_when_the_environment_has_none():
    provider = LayeredMailConfigProvider({})
    provider.stored = SAVED
    assert provider.get() == SAVED and provider.source() == "store"


def test_the_platform_mail_environment_wins_over_the_saved_settings():
    provider = LayeredMailConfigProvider(
        {"MAIL_SMTP_SERVER": "env.example.org", "MAIL_SENDER": "e@example.org"}
    )
    provider.stored = SAVED
    assert provider.get().smtp_server == "env.example.org" and provider.source() == "environment"


def test_the_admin_mail_environment_wins_over_the_platform_one():
    provider = LayeredMailConfigProvider(
        {
            "MAIL_SMTP_SERVER": "env.example.org",
            "MAIL_SENDER": "e@example.org",
            "ADMIN_MAIL_SMTP_SERVER": "admin.example.org",
            "ADMIN_MAIL_SENDER": "a@example.org",
            "ADMIN_MAIL_SMTP_PORT": "2525",
        }
    )
    provider.stored = SAVED
    got = provider.get()
    assert (got.smtp_server, got.sender, got.smtp_port) == (
        "admin.example.org", "a@example.org", 2525,
    )


def test_a_config_from_saved_settings_keeps_defaults_for_missing_keys():
    config = mail_config_from_settings(
        {"ADMIN_MAIL_SMTP_SERVER": "s.example.org", "ADMIN_MAIL_SENDER": "x@example.org"}
    )
    assert config.configured and config.smtp_port == 587 and config.starttls
    assert not config.ssl_tls and config.validate_certs


async def test_a_mailer_with_candidate_settings_sends_with_exactly_those():
    seen = []

    class Transport:
        def __init__(self, config):
            seen.append(config)

        async def send(self, to, subject, body):
            return None

    base = AdminMailer(transport_factory=Transport)
    candidate = MailConfig(smtp_server="candidate.example.org", sender="c@example.org")
    assert await base.with_config(candidate).send_message("a@example.org", Message("s", "b"))
    assert seen == [candidate]


async def test_the_refresher_runs_before_a_send_and_its_failure_is_not_fatal():
    calls = []

    async def refresh():
        calls.append(1)
        raise RuntimeError("store down")

    class Transport:
        def __init__(self, config):
            pass

        async def send(self, to, subject, body):
            return None

    provider = LayeredMailConfigProvider({})
    provider.stored = SAVED
    mailer = AdminMailer(provider, Transport, refresh=refresh)
    assert await mailer.send_message("a@example.org", Message("s", "b"))
    assert calls == [1]
