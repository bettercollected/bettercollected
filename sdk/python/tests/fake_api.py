"""A mocked public API for the tests: an in-memory server behind
``httpx.MockTransport`` that keeps forms with versions, enforces If-Match
and answers errors in the API's shape."""

from __future__ import annotations

import json
from typing import Any

import httpx

PREFIX = "/api/v1/public/v1"
KEY = "bc_" + "0" * 64


def _fields(document: dict) -> dict[str, dict]:
    found: dict[str, dict] = {}

    def walk(fields) -> None:
        for field in fields or []:
            found[field["id"]] = field
            walk(field.get("fields"))

    for page in document.get("pages") or []:
        walk(page.get("fields"))
    return found


class FakeApi:
    """One workspace of one instance. ``key`` is the only key it accepts;
    ``refuse_types`` are question types this instance has switched off."""

    def __init__(self, key: str = KEY, refuse_types: tuple[str, ...] = ()) -> None:
        self.key = key
        self.refuse_types = refuse_types
        # a key an admin limited to certain forms: it cannot create a form
        self.cannot_create = False
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

    def problems(self, body: dict) -> list[dict]:
        errors = []
        if body.get("specVersion") != "1":
            errors.append({"path": "/specVersion", "message": "Input should be '1'"})
        for index, page in enumerate(body.get("pages") or []):
            for at, field in enumerate(page.get("fields") or []):
                if field.get("type") in self.refuse_types:
                    errors.append(
                        {
                            "path": f"/pages/{index}/fields/{at}/type",
                            "message": f"{field['type']} questions are not enabled here.",
                        }
                    )
        return errors

    @staticmethod
    def merged(before: dict, body: dict) -> dict:
        """A replace keeps a ``trust`` or ``logo`` key the document leaves out."""
        result = dict(body)
        for part in ("trust", "logo"):
            if isinstance(before.get(part), dict) and part in body:
                result[part] = {**before[part], **(body[part] or {})}
            elif part in before and part not in body:
                result[part] = before[part]
        return result

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("Authorization") != f"Bearer {self.key}":
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
            errors = self.problems(body)
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
            if self.cannot_create:
                return self.error(
                    403,
                    "key_form_scope",
                    "This API key is limited to certain forms, so it cannot "
                    "create a form.",
                )
            errors = self.problems(body)
            if errors:
                return self.error(
                    422, "invalid_spec", "The document is not valid.", errors=errors
                )
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
            self.forms[form_id] = self.merged(self.forms[form_id], body)
            self.versions[form_id] += 1
            return httpx.Response(
                200, json=self.forms[form_id], headers={"ETag": self.etag(form_id)}
            )
        if parts[2:] == ["replace", "dry-run"]:
            before = self.forms[form_id]
            after = self.merged(before, body)
            changes = [
                {"path": f"/{k}", "before": before.get(k), "after": after.get(k)}
                for k in sorted(set(before) | set(after))
                if k != "pages" and before.get(k) != after.get(k)
            ]
            old, new = _fields(before), _fields(after)
            fields = {
                "added": [
                    {"id": i, "path": f"/fields/{i}"} for i in new if i not in old
                ],
                "removed": [
                    {"id": i, "path": f"/fields/{i}"} for i in old if i not in new
                ],
                "moved": [],
                "changed": [
                    {
                        "id": i,
                        "changes": [
                            {
                                "path": f"/fields/{i}/{k}",
                                "before": old[i].get(k),
                                "after": new[i].get(k),
                            }
                            for k in sorted(set(old[i]) | set(new[i]))
                            if old[i].get(k) != new[i].get(k)
                        ],
                    }
                    for i in old
                    if i in new and old[i] != new[i]
                ],
            }
            changed = bool(
                changes or fields["added"] or fields["removed"] or fields["changed"]
            )
            errors = self.problems(body)
            return httpx.Response(
                200,
                json={
                    "valid": not errors,
                    "errors": errors,
                    "warnings": [],
                    "form": after,
                    "diff": {
                        "form": changes,
                        "pages": {
                            "added": [],
                            "removed": [],
                            "moved": [],
                            "changed": [],
                        },
                        "fields": fields,
                        "changed": changed,
                    },
                },
            )
        if parts[2:] == ["submissions"] and method == "POST":
            if not body.get("consent"):
                return self.error(
                    422, "consent_required", "Send consent: true."
                )
            self.submissions = getattr(self, "submissions", {})
            response_id = f"r{len(self.submissions) + 1}"
            self.submissions[response_id] = body["answers"]
            self.consent_items = body.get("consentItems")
            return httpx.Response(
                201,
                json={
                    "responseId": response_id,
                    "formId": form_id,
                    "submittedAt": "2026-11-01T10:00:00+00:00",
                    "formVersion": 1,
                },
            )
        if len(parts) == 4 and parts[2] == "submissions" and method == "PATCH":
            stored = getattr(self, "submissions", {})
            if parts[3] not in stored:
                return self.error(404, "not_found", "Response not found")
            stored[parts[3]] = {**stored[parts[3]], **body["answers"]}
            return httpx.Response(
                200, json={"responseId": parts[3], "updatedAt": None}
            )
        if parts[2:] == ["ops"]:
            return self.error(
                422,
                "ops_failed",
                "An operation failed, so none was applied.",
                errors=[{"path": "/ops/0", "message": "No such field."}],
            )
        return self.error(404, "not_found", "Not found")
