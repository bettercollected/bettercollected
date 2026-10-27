"""A fake Objects API for the registration tests (synthetic data only).

It behaves like the real one where the registration code depends on it:
the token is checked, ``POST objects`` needs ``Content-Crs`` and a body of
``{type, record: {typeVersion, data, startAt}}`` and answers 201 with an object
carrying a UUID; ``GET objects`` filters by ``type`` and a ``data_attr``
expression (``key__nested__exact__value``, ``data @> {...}`` semantics), refuses
a malformed expression with 400 and honours ``pageSize``.

Switches make it misbehave the way a real service can: ``ignore_filter`` (the
filter parameter is not applied: every object of the type is listed),
``drop_reply`` (the object is created, the reply is lost), a canned answer for
any method, and a schema that refuses data.
"""

import json
import re
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlsplit

TOKEN = "t0ken-for-tests"
BASE_PATH = "/api/v2/"
TYPE_URL = (
    "https://types.example.org/api/v2/objecttypes/3f5e8a10-0b1c-4d2e-9a3b-5c6d7e8f9a0b"
)
OPERATORS = {"exact", "icontains", "in", "gt", "gte", "lt", "lte"}


def nested(path: List[str], value: Any) -> dict:
    for key in reversed(path):
        value = {key: value}
    return value


def contains(data: Any, probe: Any) -> bool:
    """``data @> probe``."""
    if isinstance(probe, dict):
        return isinstance(data, dict) and all(
            k in data and contains(data[k], v) for k, v in probe.items()
        )
    return data == probe


class FakeObjectsApi:
    def __init__(self):
        self.objects: List[dict] = []
        self.token = TOKEN
        self.ignore_filter = False
        self.drop_reply_next = 0
        self.canned: Dict[str, Optional[tuple]] = {}  # method -> answer
        self.required: List[str] = []  # top-level data keys the "schema" demands
        self.created = 0
        self.rejected_headers: List[str] = []

    # the TlsServer handler
    def handle(self, request):
        parts = urlsplit(request.target)
        if request.headers.get("authorization") != f"Token {self.token}":
            return self._json(401, {"detail": "no"})
        if not parts.path.startswith(BASE_PATH + "objects"):
            return self._json(404, {})
        if request.method in self.canned and self.canned[request.method] is not None:
            return self.canned[request.method]
        if request.method == "POST":
            return self._create(request)
        if request.method == "GET":
            return self._list(parts.query)
        return self._json(405, {})

    @staticmethod
    def _json(status: int, body: Any, extra: Optional[dict] = None):
        return (
            status,
            {"Content-Type": "application/json", **(extra or {})},
            json.dumps(body).encode(),
        )

    def _create(self, request):
        if request.headers.get("content-crs") != "EPSG:4326":
            return self._json(400, {"detail": "Content-Crs missing"})
        try:
            body = json.loads(request.body)
            record = body["record"]
            ok = (
                isinstance(body["type"], str)
                and isinstance(record["typeVersion"], int)
                and isinstance(record["data"], dict)
                and re.match(r"^\d{4}-\d{2}-\d{2}$", record["startAt"])
                and "geometry" not in record
            )
        except (ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            return self._json(400, {"detail": "shape"})
        missing = [k for k in self.required if record["data"].get(k) is None]
        if missing:
            return self._json(400, {"invalid-params": [{"name": "data"}]})
        item = {
            "url": f"https://case.example.org{BASE_PATH}objects/x",
            "uuid": str(uuid.uuid4()),
            "type": body["type"],
            "record": {**record, "index": 1},
        }
        self.objects.append(item)
        self.created += 1
        if self.drop_reply_next:
            self.drop_reply_next -= 1
            return None
        return self._json(201, item)

    def _list(self, query: str):
        pairs = parse_qsl(query, keep_blank_values=True)
        params: Dict[str, List[str]] = {}
        for key, value in pairs:
            params.setdefault(key, []).append(value)
        if "type" not in params:
            return self._json(400, {"detail": "type"})
        expressions = params.get("data_attr", [])
        for expression in expressions:
            bits = expression.rsplit("__", 2)
            if len(bits) != 3 or bits[1] not in OPERATORS:
                if not self.ignore_filter:
                    return self._json(400, {"detail": "filter"})
        results = [o for o in self.objects if o["type"] == params["type"][0]]
        if not self.ignore_filter:
            for expression in expressions:
                key, operator, value = expression.rsplit("__", 2)
                assert operator == "exact", operator
                probe = nested(key.split("__"), value)
                results = [o for o in results if contains(o["record"]["data"], probe)]
        size = int(params.get("pageSize", ["100"])[0])
        shown = results if self.ignore_filter else results[:size]
        return self._json(
            200,
            {"count": len(results), "next": None, "previous": None, "results": shown},
        )
