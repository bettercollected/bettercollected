"""The catalogue of listed event kinds: every kind the schema defines is in
exactly one area (or is an account-level kind no workspace feed lists), so a
kind added to the schema cannot ship unlisted."""

import pytest

from backend.app.schemas import workspace_audit_event as schema
from backend.app.services.audit_log import catalog

# string constants of the schema module that are not event kinds
NOT_KINDS = {"NO_WORKSPACE"}
NOT_KIND_PREFIXES = ("REVOKED_",)  # the reasons of API_KEY_REVOKED


def schema_kinds() -> set:
    return {
        value
        for name, value in vars(schema).items()
        if name.isupper()
        and isinstance(value, str)
        and name not in NOT_KINDS
        and not name.startswith(NOT_KIND_PREFIXES)
    }


def test_every_kind_of_the_schema_is_in_exactly_one_area_or_is_account_level():
    kinds = schema_kinds()
    assert kinds, "the schema's kinds were not found"
    listed = [kind for area in catalog.AREAS.values() for kind in area]
    assert len(listed) == len(set(listed)), "a kind is in two areas"
    assert not set(listed) & catalog.ACCOUNT_LEVEL
    assert set(listed) | catalog.ACCOUNT_LEVEL == kinds, kinds ^ (
        set(listed) | catalog.ACCOUNT_LEVEL
    )


def test_the_schemas_own_groups_are_covered():
    groups = (
        schema.SSO_EVENTS,
        schema.TOTP_EVENTS,
        schema.ACCESS_EVENTS,
        schema.MEMBER_FORM_EVENTS,
        schema.API_KEY_EVENTS,
        schema.SETTINGS_EVENTS,
        schema.AUTOMATION_EVENTS,
    )
    for group in groups:
        for kind in group:
            assert kind in catalog.LISTED or kind in catalog.ACCOUNT_LEVEL, kind


def test_the_account_level_kinds_are_second_factor_events_of_one_person():
    assert catalog.ACCOUNT_LEVEL <= set(schema.TOTP_EVENTS)
    assert not catalog.ACCOUNT_LEVEL & catalog.LISTED


def test_kinds_of_names_areas_and_kinds_and_refuses_what_it_does_not_know():
    assert set(catalog.kinds_of()) == catalog.LISTED
    assert set(catalog.kinds_of(["members"])) == set(catalog.AREAS["members"])
    assert set(catalog.kinds_of(["members"], [schema.TEAM_CREATED])) == set(
        catalog.AREAS["members"]
    ) | {schema.TEAM_CREATED}
    for areas, events in ((["nope"], None), (None, ["nope"]), (None, [schema.TOTP_ENROLLED])):
        with pytest.raises(ValueError):
            catalog.kinds_of(areas, events)
    assert catalog.area_of(schema.MEMBER_REMOVED) == "members"
    assert catalog.area_of(schema.TOTP_ENROLLED) is None
