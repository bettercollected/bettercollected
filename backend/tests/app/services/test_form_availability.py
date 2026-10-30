"""The close date of a form, read one way (services/form_availability.py)."""

import datetime as dt
from http import HTTPStatus

import pytest
from pydantic import ValidationError

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.settings_patch import SettingsPatchDto
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.services import form_availability
from backend.app.services.form_availability import (
    closes_at,
    ensure_accepting_responses,
    is_closed,
    normalized_close_date,
    parse_instant,
)

UTC = dt.timezone.utc
CLOSE = dt.datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)
SECOND = dt.timedelta(seconds=1)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-10-30T12:00:00+00:00", CLOSE),
        ("2026-10-30T12:00:00Z", CLOSE),
        ("2026-10-30T12:00:00.000Z", CLOSE),
        ("2026-10-30T12:00:00.250Z", CLOSE + dt.timedelta(milliseconds=250)),
        ("2026-10-30T14:00:00+02:00", CLOSE),
        ("2026-10-30T07:00:00-05:00", CLOSE),
        # no offset: UTC, as the webapp reads it
        ("2026-10-30T12:00:00", CLOSE),
        ("2026-10-30", dt.datetime(2026, 10, 30, tzinfo=UTC)),
        (" 2026-10-30T12:00:00Z ", CLOSE),
        (dt.datetime(2026, 10, 30, 12), CLOSE),
        (dt.datetime(2026, 10, 30, 14, tzinfo=dt.timezone(dt.timedelta(hours=2))), CLOSE),
    ],
)
def test_close_dates_in_every_spelling_name_the_same_instant(value, expected):
    assert parse_instant(value) == expected
    assert closes_at(WorkspaceFormSettings(form_close_date=value)) == expected
    assert closes_at({"form_close_date": value}) == expected


@pytest.mark.parametrize(
    "value",
    ["", "   ", None, "banana", "2026-13-45T00:00:00", "30/10/2026", 1730289600, [], {}],
)
def test_empty_and_unreadable_values_mean_no_close_date(value):
    assert parse_instant(value) is None
    assert closes_at({"form_close_date": value}) is None
    assert not is_closed({"form_close_date": value}, CLOSE)
    ensure_accepting_responses({"form_close_date": value}, CLOSE)


def test_no_settings_mean_open():
    assert not is_closed(None, CLOSE)
    assert not is_closed({}, CLOSE)
    assert not is_closed(WorkspaceFormSettings(), CLOSE)


@pytest.mark.parametrize(
    "value", ["2026-10-30T12:00:00Z", "2026-10-30T14:00:00+02:00", "2026-10-30T12:00:00"]
)
def test_a_form_closes_on_the_close_instant_itself(value):
    settings = {"form_close_date": value}
    assert not is_closed(settings, CLOSE - SECOND)
    assert not is_closed(settings, CLOSE - dt.timedelta(microseconds=1))
    assert is_closed(settings, CLOSE)
    assert is_closed(settings, CLOSE + SECOND)


def test_the_gate_refuses_with_409_form_closed_from_the_close_instant():
    settings = WorkspaceFormSettings(form_close_date="2026-10-30T14:00:00+02:00")
    ensure_accepting_responses(settings, CLOSE - SECOND)
    for now in (CLOSE, CLOSE + SECOND):
        with pytest.raises(HTTPException) as refused:
            ensure_accepting_responses(settings, now)
        assert refused.value.status_code == HTTPStatus.CONFLICT
        assert refused.value.content == {
            "code": "form_closed",
            "message": "This form is closed and no longer accepts responses.",
            "closesAt": "2026-10-30T12:00:00+00:00",
        }


def test_without_a_time_given_the_server_clock_decides(monkeypatch):
    settings = {"form_close_date": "2026-10-30T12:00:00Z"}
    monkeypatch.setattr("common.clock.utcnow", lambda: CLOSE - SECOND)
    assert form_availability.now() == CLOSE - SECOND
    assert not is_closed(settings)
    ensure_accepting_responses(settings)
    monkeypatch.setattr("common.clock.utcnow", lambda: CLOSE)
    assert is_closed(settings)
    with pytest.raises(HTTPException):
        ensure_accepting_responses(settings)


@pytest.mark.parametrize(
    "value, stored",
    [
        (None, None),
        ("", ""),
        ("  ", ""),
        ("2026-10-30T12:00:00.000Z", "2026-10-30T12:00:00+00:00"),
        ("2026-10-30T12:00:00.250Z", "2026-10-30T12:00:00.250000+00:00"),
        ("2026-10-30T14:00:00+02:00", "2026-10-30T12:00:00+00:00"),
        ("2026-10-30T12:00:00", "2026-10-30T12:00:00+00:00"),
        (dt.datetime(2026, 10, 30, 12, tzinfo=UTC), "2026-10-30T12:00:00+00:00"),
    ],
)
def test_the_settings_patch_stores_a_utc_instant(value, stored):
    assert normalized_close_date(value) == stored
    assert SettingsPatchDto(formCloseDate=value).form_close_date == stored
    if stored:
        # what is stored reads back as the instant that was sent
        assert parse_instant(stored) == parse_instant(value)


@pytest.mark.parametrize(
    "value",
    ["banana", "2026-13-45T00:00:00", "30/10/2026", "2026-10-30T12:00:00Z" + "0" * 80, 1730289600, True],
)
def test_the_settings_patch_refuses_what_is_not_a_date(value):
    with pytest.raises(ValueError):
        normalized_close_date(value)
    with pytest.raises(ValidationError):
        SettingsPatchDto(formCloseDate=value)
