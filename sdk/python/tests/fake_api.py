"""A mocked public API for the tests: an in-memory server behind
``httpx.MockTransport`` that keeps forms with versions, enforces If-Match
and answers errors in the API's shape."""

from __future__ import annotations

import json
from typing import Any

import httpx

PREFIX = "/api/v1/public/v1"
KEY = "bc_" + "0" * 64


class FakeApi:
    def __init__(self) -> None:
        self.forms: dict[str, dict] = {}
        self.versions: dict[str, int] = {}
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def etag(self, form_id: str) -> str:
        return f'"{self.versions[form_id]}-test"'

    def add(self, form_id: str, document: dict) -> None:
        self.forms[form_id] = document
        self.versions[form_id] = 1

    def change_on_server(self, form_id: str, **changes: Any) -> None:
        self.forms[form_id] = {**self.forms[form_id], **changes}
        self.versions[form_id] += 1

    @staticmethod
    def error(status: int, code: str, message: str, **extra) -> httpx.Response:
        return httpx.Response(status, json={"code": code, "message": message, **extra})

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("Authorization") != f"Bearer {KEY}":
            return self.error(401, "unauthorized", "Provide a valid workspace API key.")
        assert request.url.path.startswith(PREFIX)
        parts = request.url.path[len(PREFIX) :].strip("/").split("/")
        body = json.loads(request.content) if request.content else None
        method = request.method

        if parts == ["forms"] and method == "GET":
            items = [
                {"formId": i, "title": d.get("title"), "published": False}
                for i, d in self.forms.items()
            ]
            return httpx.Response(
                200, json={"items": items, "page": 1, "size": 50, "total": len(items)}
            )
        if parts == ["forms", "validate"]:
            errors = []
            if body.get("specVersion") != "1":
                errors.append(
                    {"path": "/specVersion", "message": "Input should be '1'"}
                )
            return httpx.Response(
                200,
                json={
                    "valid": not errors,
                    "errors": errors,
                    "warnings": [],
                    "compliance": {"checked": False},
                },
            )
        if parts == ["forms"] and method == "POST":
            form_id = f"f{len(self.forms) + 1}"
            self.add(form_id, body)
            return httpx.Response(
                201,
                json={"formId": form_id, "form": body},
                headers={"ETag": self.etag(form_id)},
            )
        if len(parts) >= 2 and parts[1] not in self.forms:
            return self.error(404, "not_found", "Form not found")
        form_id = parts[1]
        if len(parts) == 2 and method == "GET":
            return httpx.Response(
                200, json=self.forms[form_id], headers={"ETag": self.etag(form_id)}
            )
        if len(parts) == 2 and method == "PUT":
            if_match = request.headers.get("If-Match")
            if not if_match:
                return self.error(428, "precondition_required", "Send If-Match.")
            if if_match != self.etag(form_id):
                return self.error(412, "precondition_failed", "The form changed.")
            self.forms[form_id] = body
            self.versions[form_id] += 1
            return httpx.Response(200, json=body, headers={"ETag": self.etag(form_id)})
        if parts[2:] == ["replace", "dry-run"]:
            before = self.forms[form_id]
            changes = [
                {"path": f"/{k}", "before": before.get(k), "after": body.get(k)}
                for k in sorted(set(before) | set(body))
                if k != "pages" and before.get(k) != body.get(k)
            ]
            diff = {
                "form": changes,
                "pages": {"added": [], "removed": [], "moved": [], "changed": []},
                "fields": {"added": [], "removed": [], "moved": [], "changed": []},
                "changed": bool(changes),
            }
            return httpx.Response(
                200,
                json={
                    "valid": True,
                    "errors": [],
                    "warnings": [],
                    "form": body,
                    "diff": diff,
                },
            )
        if parts[2:] == ["ops"]:
            return self.error(
                422,
                "ops_failed",
                "An operation failed, so none was applied.",
                errors=[{"path": "/ops/0", "message": "No such field."}],
            )
        return self.error(404, "not_found", "Not found")
