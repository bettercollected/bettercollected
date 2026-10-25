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


def test_echo_free_removes_whole_tokens_only():
    # a submitted value inside a longer word leaves the word alone
    assert echo_free("format is not valid", "mat") == "format is not valid"
    assert echo_free("the table is not a tab", ["tab"]) == "the table is not a …"
    assert echo_free("pattern_x and x_pattern", "pattern") == "pattern_x and x_pattern"
    # at the ends of the message, next to punctuation and quotes, it still goes
    assert echo_free("secret", "secret") == "…"
    assert echo_free("bad (secret), secret.", "secret") == "bad (…), …."
    assert echo_free("saw 'tokensecret' here", "tokensecret") == "saw '…' here"
    # values with punctuation of their own, and several at once, longest first
    assert echo_free("rejected p@ss!w0rd and p@ss", ["p@ss", "p@ss!w0rd"]) == "rejected … and …"
    assert echo_free("a.b.c is not a.b", ["a.b.c", "a.b"]) == "… is not …"
    # regex characters in the submitted value are literal
    assert echo_free("saw .* and (x+", [".*x", "(x+", ".*"]) == "saw .* and …"  # ".*": short, only quoted
    assert echo_free("saw abc here", [".*c"]) == "saw abc here"
