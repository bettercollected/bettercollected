"""The shared 422 handler never sends a submitted value back, not even through a
custom validator that put it into its own message."""

from typing import List

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator

from common.exceptions.validation import echo_free, request_validation_error_handler


class Spec(BaseModel):
    pattern: str
    statuses: List[str] = []

    @field_validator("pattern")
    @classmethod
    def _pattern(cls, value: str) -> str:
        if not value.startswith("^"):
            raise ValueError(f"'{value}' is not a valid pattern (must start with ^).")
        return value

    @field_validator("statuses")
    @classmethod
    def _statuses(cls, values: List[str]) -> List[str]:
        seen = set()
        for status in values:
            if status in seen:
                raise ValueError(f"The status '{status}' is listed twice.")
            seen.add(status)
        return values


@pytest.fixture
def client():
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)

    @app.post("/spec")
    async def post(spec: Spec):
        return {"ok": True}

    return TestClient(app)


def test_a_custom_validator_message_does_not_echo_a_string_input(client):
    secret = "hunter2-visible-in-the-pattern"
    body = client.post("/spec", json={"pattern": secret}).text
    assert secret not in body
    assert "is not a valid pattern" in body  # the useful part of the message stays


def test_a_custom_validator_message_does_not_echo_strings_of_a_list_input(client):
    body = client.post("/spec", json={"pattern": "^ok", "statuses": ["confidential-status", "confidential-status"]}).text
    assert "confidential-status" not in body
    assert "listed twice" in body


def test_the_shape_and_the_fixed_fields_are_kept(client):
    data = client.post("/spec", json={"pattern": "plain-text-value"}).json()
    item = data["detail"][0]
    assert set(item) == {"loc", "msg", "type"} and item["loc"][-1] == "pattern"
    assert "input" not in item and "ctx" not in item


def test_echo_free_removes_nested_strings_and_short_quoted_ones_only():
    assert echo_free("bad 'ab' in the ab words", ["ab"]) == "bad '…' in the ab words"
    assert echo_free("saw tokensecret here", {"k": ["tokensecret"]}) == "saw … here"
    assert echo_free("no input", None) == "no input"
    assert echo_free("x", 5) == "x"
