"""What single sign-on needs per service, by name (common/settings/sso_requirements)."""

from common.settings import sso_requirements as req
from common.settings.inventory import all_specs


def test_every_required_name_is_a_known_setting_read_by_that_service():
    specs = {s.key: s for s in all_specs()}
    for table in (req.REQUIRED, req.OPTIONAL):
        for service, names in table.items():
            for name in names:
                assert service in specs[name].readers, (service, name)
    assert req.ENABLED_KEY in specs


def test_missing_and_status():
    nothing = lambda name: False  # noqa: E731
    everything = lambda name: True  # noqa: E731
    assert req.missing("backend", nothing) == req.REQUIRED["backend"]
    assert req.missing("backend", everything) == ()
    assert req.missing("unknown-service", nothing) == ()
    assert req.missing_optional("auth", nothing) == ("SSO_POLIS_CLIENT_SECRET",)
    assert req.status(False, ("SSO_POLIS_URL",)) == "disabled"
    assert req.status(True, ("SSO_POLIS_URL",)) == "not_configured"
    assert req.status(True, ()) is None


def test_startup_message_is_names_only():
    message = req.startup_message("backend", ("SSO_POLIS_URL", "SSO_REDIRECT_URI"))
    assert "missing SSO_POLIS_URL, SSO_REDIRECT_URI." in message
    assert "backend" in message and "://" not in message
