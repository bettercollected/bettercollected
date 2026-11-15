"""``APP_THEME_PIGMENT_ENABLED`` is an ordinary stored setting (tier T2, class R, default off), read like
``CAPTCHA_ENABLED`` and ``DAYBREAK_PRESET_ENABLED``: a non-empty environment value, then the value an instance
admin stored in the admin portal, then the default. These tests turn it on and off through the stored value (a
loader runtime with a stored row, not a monkeypatch of the group) and check what each state means: the
off-by-default behaviour of ``docs/app-theme.md``, and the on state's offers."""

import pytest
from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
)
from common.settings.inventory import T2, Reload, all_specs

from backend.app.constants.themes import (
    artwork_offered,
    offered_theme_keys,
    preset_offered,
    theme_dict,
    theme_key_offered,
)
from backend.app.container import container
from backend.app.services.app_theme.mode import app_theme_pigment_enabled, effective_theme
from backend.app.services.form_writes import persist_form
from backend.config import settings
from backend.config.app_theme_settings import AppThemeSettings
from tests.app.controllers.data import testUser
from tests.app.app_theme.test_app_theme import (
    choose,
    lookup,
    stored_theme,
)

KEY = "APP_THEME_PIGMENT_ENABLED"
PIGMENT = dict(theme_dict["Pigment"])


class _Resolved:
    def __init__(self, value):
        self.value = value


class _Runtime:
    """What ``StoreSource`` asks the loader's runtime: the verified row of a key, and the keys that have one."""

    def __init__(self, stored):
        self.stored = stored
        self.current = {key: object() for key in stored}

    def resolve_key(self, key):
        return _Resolved(self.stored[key]) if key in self.stored else None


@pytest.fixture
def stored(monkeypatch):
    """``stored(True)`` / ``stored(False)`` / ``stored(None)``: the admin portal's value, read the way the backend reads it at
    start-up (a new ``AppThemeSettings`` under a loader runtime), and now the backend's group."""
    monkeypatch.delenv(KEY, raising=False)

    def set_to(value):
        runtime = _Runtime({} if value is None else {KEY: value})
        monkeypatch.setattr("common.settings.loader.pydantic_source.current_runtime", lambda: runtime)
        monkeypatch.setattr(settings, "app_theme", AppThemeSettings())

    return set_to


# ------------------------------------------------------------------------------------------ the setting


def test_it_is_a_stored_setting_of_tier_t2_default_off():
    (spec,) = [s for s in all_specs() if s.key == KEY]
    assert spec.tier == T2 and spec.default is False and spec.reload_class == Reload.R
    # the same shape as the two switches it follows
    for other in ("CAPTCHA_ENABLED", "DAYBREAK_PRESET_ENABLED"):
        (twin,) = [s for s in all_specs() if s.key == other]
        assert (twin.tier, twin.reload_class, twin.default, twin.readers) == (spec.tier, spec.reload_class, spec.default, spec.readers)
    assert "Environment only" not in spec.description
    # backend only: the inventory and the readers guard (common/tests/settings/test_switch_readers.py) agree
    assert spec.readers == ("backend",)


def test_off_by_default_with_no_environment_value_and_no_stored_row(stored):
    stored(None)
    assert AppThemeSettings().ENABLED is False
    assert app_theme_pigment_enabled() is False


def test_a_stored_value_turns_it_on_and_off(stored):
    stored(True)
    assert settings.app_theme.ENABLED is True and app_theme_pigment_enabled() is True
    stored(False)
    assert settings.app_theme.ENABLED is False and app_theme_pigment_enabled() is False


def test_the_order_is_environment_then_stored_then_default(stored, monkeypatch):
    stored(True)
    # a non-empty environment value wins over the stored one, either way
    monkeypatch.setenv(KEY, "false")
    assert AppThemeSettings().ENABLED is False
    stored(False)
    monkeypatch.setenv(KEY, "true")
    assert AppThemeSettings().ENABLED is True
    # an empty environment value does not shadow a stored row (the loader's rule for every stored setting)
    monkeypatch.setenv(KEY, "")
    stored(True)
    monkeypatch.setenv(KEY, "")
    assert AppThemeSettings().ENABLED is True


# ------------------------------------------------------------------- turned on through the stored setting


async def test_stored_on_the_choice_is_accepted_and_the_pigment_offers_appear(
    client, workspace, test_user_cookies, stored
):
    stored(True)
    permissions = (await client.get(f"/api/v1/workspaces/{workspace.id}/permissions", cookies=test_user_cookies)).json()
    assert permissions["appThemeEnabled"] is True
    assert "Pigment" in permissions["offeredGatedPresets"]
    assert preset_offered("Pigment") and artwork_offered("pigment") and theme_key_offered("choiceKeys")
    assert "choiceKeys" in offered_theme_keys()

    chosen = await choose(client, workspace, test_user_cookies, "pigment")
    assert chosen.status_code == 200 and chosen.json() == {"appTheme": "pigment"}
    assert (await lookup(client, workspace, test_user_cookies)).json()["appTheme"] == "pigment"
    assert effective_theme("pigment") == "pigment"


# ------------------------------------------------------------------ turned off again through the stored value


async def test_stored_off_again_a_pigment_workspace_is_served_daybreak_and_keeps_its_choice(
    client, workspace, test_user_cookies, stored
):
    stored(True)
    assert (await choose(client, workspace, test_user_cookies, "pigment")).status_code == 200

    stored(False)
    answer = await client.get(f"/api/v1/workspaces/{workspace.id}/permissions", cookies=test_user_cookies)
    assert answer.json()["appThemeEnabled"] is False and "Pigment" not in answer.json()["offeredGatedPresets"]
    assert (await lookup(client, workspace, test_user_cookies)).json()["appTheme"] == "daybreak"
    # kept, neither enforced nor shown; nothing was deleted
    assert await stored_theme(workspace) == "pigment"
    # only choosing it anew is refused
    refused = await choose(client, workspace, test_user_cookies, "pigment")
    assert refused.status_code == 422 and refused.json()["code"] == "app_theme_disabled"
    assert await stored_theme(workspace) == "pigment"
    assert not preset_offered("Pigment") and not artwork_offered("pigment") and not theme_key_offered("choiceKeys")

    # turned on again: the workspace is Pigment again, as it was
    stored(True)
    assert (await lookup(client, workspace, test_user_cookies)).json()["appTheme"] == "pigment"


def _form(theme):
    from common.models.standard_form import Theme

    return StandardForm(
        title="Form",
        theme=Theme(**theme),
        fields=[
            StandardFormField(
                id="page-1",
                type=T.SLIDE,
                properties=StandardFieldProperty(
                    fields=[StandardFormField(id="q1", index=0, type=T.SHORT_TEXT, title="Your name")]
                ),
            )
        ],
    )


async def test_stored_off_again_a_form_that_wears_the_pigment_preset_still_saves(workspace, stored):
    stored(True)
    created = await container.workspace_form_service().create_form(workspace.id, _form(PIGMENT), testUser)
    repo = container.form_repo()
    document = await repo.get_form_document_by_id(str(created.form_id))

    stored(False)
    # what the form already wears still saves (a changed title, the same preset, artwork and keys)
    assert await persist_form(repo, document, _form({**PIGMENT, "title": "Mine"}), parts=["theme"])
