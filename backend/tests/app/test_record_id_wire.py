"""Switching an endpoint from ``PydanticObjectId`` to ``RecordId`` (common/common/ids.py)
changes nothing on the wire: the same responses, the same 422 bodies and the
same OpenAPI document, for ids in paths, queries, bodies and responses."""

from typing import List, Optional

import pytest
from beanie import PydanticObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from common.ids import RecordId

HEX = "65f0a1b2c3d4e5f601234567"


def _app(id_type) -> FastAPI:
    class Item(BaseModel):
        id: id_type
        parent_id: Optional[id_type] = None
        related: List[id_type] = []

    app = FastAPI()

    @app.get("/items/{item_id}", response_model=Item)
    def get_item(item_id: id_type, parent: Optional[id_type] = None):
        return Item(id=item_id, parent_id=parent)

    @app.post("/items", response_model=Item)
    def post_item(item: Item):
        return item

    @app.get("/raw/{item_id}")
    def raw(item_id: id_type):
        return {"id": item_id, "type_ok": isinstance(item_id, id_type)}

    return app


OLD = TestClient(_app(PydanticObjectId), raise_server_exceptions=False)
NEW = TestClient(_app(RecordId), raise_server_exceptions=False)

REQUESTS = [
    ("get", f"/items/{HEX}", None),
    ("get", f"/items/{HEX}?parent={HEX}", None),
    ("get", f"/items/{HEX.upper()}", None),
    ("get", "/items/not-an-id", None),
    ("get", f"/items/{HEX}?parent=nope", None),
    ("get", f"/raw/{HEX}", None),
    ("get", "/raw/123", None),
    ("post", "/items", {"id": HEX, "related": [HEX, HEX]}),
    ("post", "/items", {"id": HEX.upper(), "parent_id": None}),
    ("post", "/items", {"id": "short"}),
    ("post", "/items", {"id": 12}),
    ("post", "/items", {"id": HEX, "related": ["x"]}),
    ("post", "/items", {"id": {"$oid": HEX}}),
]


@pytest.mark.parametrize("method, url, body", REQUESTS)
def test_responses_are_identical(method, url, body):
    old = OLD.request(method, url, json=body)
    new = NEW.request(method, url, json=body)
    assert (new.status_code, new.text) == (old.status_code, old.text)


def test_a_bare_id_in_an_untyped_response_is_written_as_before():
    # FastAPI has no encoder for ObjectIds: a bare one becomes {} (a quirk the
    # switch keeps; typed responses, the norm, write the hex string)
    assert NEW.get(f"/raw/{HEX}").json() == {"id": {}, "type_ok": True}


def test_a_malformed_id_gets_the_same_422_message():
    body = NEW.get("/items/not-an-id").json()
    assert body["detail"][0]["msg"] == (
        "Value error, Id must be of type PydanticObjectId"
    )


def test_the_openapi_document_is_identical():
    assert NEW.app.openapi() == OLD.app.openapi()
    assert "PydanticObjectId" in NEW.app.openapi()["components"]["schemas"]
