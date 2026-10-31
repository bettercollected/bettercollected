"""The open date and the response limit of a form, read one way
(services/form_availability.py): the same module as the close date."""

import datetime as dt
from http import HTTPStatus

import pytest
from pydantic import ValidationError

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.settings_patch import SettingsPatchDto
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.services.form_availability import (
    MAX_RESPONSE_LIMIT,
    date_unavailability,
    ensure_accepting_responses,
    ensure_dates_in_order,
    ensure_not_full,
    is_full,
    is_unavailable_by_date,
    normalized_open_date,
    normalized_response_limit,
    opens_at,
    response_limit,
)

UTC = dt.timezone.utc
OPEN = dt.datetime(2026, 11, 2, 8, 0, 0, tzinfo=UTC)
CLOSE = dt.datetime(2026, 11, 9, 8, 0, 0, tzinfo=UTC)
SECOND = dt.timedelta(seconds=1)


@pytest.mark.parametrize(
    "value",
    [
        "2026-11-02T08:00:00Z",
        "2026-11-02T08:00:00.000Z",
        "2026-11-02T09:00:00+01:00",
        "2026-11-02T08:00:00",
        OPEN,
    ],
)
def test_an_open_date_in_every_spelling_names_the_same_instant(value):
    assert opens_at({"form_open_date": value}) == OPEN
    assert opens_at(WorkspaceFormSettings(form_open_date=value)) == OPEN


@pytest.mark.parametrize("value", ["", None, "banana", 1730289600, []])
def test_an_empty_or_unreadable_open_date_means_open_from_the_start(value):
    settings = {"form_open_date": value}
    assert opens_at(settings) is None
    assert date_unavailability(settings, OPEN - dt.timedelta(days=400)) is None
    ensure_accepting_responses(settings, OPEN - SECOND)


def test_a_form_opens_on_the_open_instant_itself():
    settings = {"form_open_date": "2026-11-02T09:00:00+01:00"}
    assert date_unavailability(settings, OPEN - SECOND) == "not_yet_open"
    assert (
        date_unavailability(settings, OPEN - dt.timedelta(microseconds=1))
        == "not_yet_open"
    )
    assert date_unavailability(settings, OPEN) is None
    assert date_unavailability(settings, OPEN + SECOND) is None


def test_the_gate_refuses_with_409_form_not_open_before_the_open_instant():
    settings = WorkspaceFormSettings(form_open_date="2026-11-02T09:00:00+01:00")
    ensure_accepting_responses(settings, OPEN)
    for now in (OPEN - SECOND, OPEN - dt.timedelta(days=30)):
        with pytest.raises(HTTPException) as refused:
            ensure_accepting_responses(settings, now)
        assert refused.value.status_code == HTTPStatus.CONFLICT
        assert refused.value.content == {
            "code": "form_not_open",
            "message": "This form is not open yet.",
            "opensAt": "2026-11-02T08:00:00+00:00",
        }


def test_open_between_the_two_dates_and_closed_wins_over_not_open():
    settings = {
        "form_open_date": OPEN.isoformat(),
        "form_close_date": CLOSE.isoformat(),
    }
    assert date_unavailability(settings, OPEN - SECOND) == "not_yet_open"
    assert date_unavailability(settings, OPEN) is None
    assert date_unavailability(settings, CLOSE - SECOND) is None
    assert date_unavailability(settings, CLOSE) == "closed"
    assert is_unavailable_by_date(settings, CLOSE)
    assert not is_unavailable_by_date(settings, OPEN + SECOND)
    # a stored pair in the wrong order (never written now): closed wins
    wrong = {"form_open_date": CLOSE.isoformat(), "form_close_date": OPEN.isoformat()}
    assert date_unavailability(wrong, OPEN - SECOND) == "not_yet_open"
    assert date_unavailability(wrong, OPEN) == "closed"
    with pytest.raises(HTTPException) as refused:
        ensure_accepting_responses(settings, CLOSE)
    assert refused.value.content["code"] == "form_closed"


def test_the_arrival_time_decides_the_open_date_too():
    settings = {"form_open_date": OPEN.isoformat()}
    # arrived before the open, handled after it: refused, as the arrival counts
    with pytest.raises(HTTPException):
        ensure_accepting_responses(settings, OPEN + SECOND, received_at=OPEN - SECOND)
    ensure_accepting_responses(settings, OPEN + SECOND, received_at=OPEN)


@pytest.mark.parametrize("value", [3, 1, MAX_RESPONSE_LIMIT])
def test_a_limit_is_a_positive_whole_number(value):
    assert response_limit({"response_limit": value}) == value
    assert response_limit(WorkspaceFormSettings(response_limit=value)) == value


@pytest.mark.parametrize("value", [None, 0, -1, "5", 2.5, True, [], {}])
def test_anything_else_stored_means_no_limit(value):
    settings = {"response_limit": value}
    assert response_limit(settings) is None
    assert not is_full(settings, 10**9)
    ensure_not_full(settings, 10**9)


def test_a_form_is_full_at_its_limit_and_not_before():
    settings = {"response_limit": 3}
    assert not is_full(settings, 0)
    assert not is_full(settings, 2)
    assert is_full(settings, 3)
    assert is_full(settings, 4)
    ensure_not_full(settings, 2)
    with pytest.raises(HTTPException) as refused:
        ensure_not_full(settings, 3)
    assert refused.value.status_code == HTTPStatus.CONFLICT
    # no number in the refusal: the count and the limit are the creator's
    assert refused.value.content == {
        "code": "form_full",
        "message": "This form has received all the responses it accepts.",
    }


@pytest.mark.parametrize(
    "value, stored",
    [
        (None, None),
        ("", ""),
        ("2026-11-02T09:00:00+01:00", "2026-11-02T08:00:00+00:00"),
        ("2026-11-02T08:00:00.000Z", "2026-11-02T08:00:00+00:00"),
        ("2026-11-02T08:00:00", "2026-11-02T08:00:00+00:00"),
    ],
)
def test_the_settings_patch_stores_the_open_date_as_a_utc_instant(value, stored):
    assert normalized_open_date(value) == stored
    assert SettingsPatchDto(formOpenDate=value).form_open_date == stored


@pytest.mark.parametrize("value", ["banana", "2026-13-45T00:00:00", 1730289600, True])
def test_the_settings_patch_refuses_an_open_date_that_is_not_a_date(value):
    with pytest.raises(ValueError, match="open date"):
        normalized_open_date(value)
    with pytest.raises(ValidationError):
        SettingsPatchDto(formOpenDate=value)


def test_an_open_date_after_the_close_date_is_refused():
    both = {
        "formOpenDate": "2026-11-09T08:00:00Z",
        "formCloseDate": "2026-11-02T08:00:00Z",
    }
    with pytest.raises(ValidationError, match="before the close date"):
        SettingsPatchDto(**both)
    with pytest.raises(ValidationError):
        SettingsPatchDto(
            formOpenDate="2026-11-02T08:00:00Z", formCloseDate="2026-11-02T08:00:00Z"
        )
    ok = SettingsPatchDto(
        formOpenDate="2026-11-02T08:00:00Z", formCloseDate="2026-11-09T08:00:00Z"
    )
    assert ok.form_open_date < ok.form_close_date
    # either alone is checked against the stored one by the service
    SettingsPatchDto(formOpenDate="2030-01-01T00:00:00Z")
    SettingsPatchDto(formCloseDate="2020-01-01T00:00:00Z")
    SettingsPatchDto(formOpenDate="", formCloseDate="2020-01-01T00:00:00Z")


def test_the_order_check_reads_the_stored_spellings():
    ensure_dates_in_order(None, None)
    ensure_dates_in_order("", "2026-11-02T08:00:00Z")
    ensure_dates_in_order("2026-11-02T09:00:00+01:00", "2026-11-02T08:00:01Z")
    with pytest.raises(ValueError):
        ensure_dates_in_order("2026-11-02T09:00:00+01:00", "2026-11-02T08:00:00Z")


@pytest.mark.parametrize(
    "value, stored",
    [
        (None, None),
        (0, 0),
        (1, 1),
        (250, 250),
        (MAX_RESPONSE_LIMIT, MAX_RESPONSE_LIMIT),
    ],
)
def test_the_settings_patch_keeps_a_whole_number_limit(value, stored):
    assert normalized_response_limit(value) == stored
    assert SettingsPatchDto(responseLimit=value).response_limit == stored


@pytest.mark.parametrize(
    "value", [-1, MAX_RESPONSE_LIMIT + 1, 2.5, "5", "", True, [], {}]
)
def test_the_settings_patch_refuses_any_other_limit(value):
    with pytest.raises(ValueError):
        normalized_response_limit(value)
    with pytest.raises(ValidationError):
        SettingsPatchDto(responseLimit=value)
