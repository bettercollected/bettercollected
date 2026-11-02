"""Builders shared by the import tests. Everything here is synthetic."""

import csv
import io
from typing import Any, Dict, List, Optional

from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from tests.app.controllers.data import testUser
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.response_export.helpers import publish as publish_form  # noqa: F401

CHOICES = [
    {"id": "c1", "value": "Red"},
    {"id": "c2", "value": "Green; dark"},
    {"id": "c3", "value": "Blue"},
]

# one question of every type the export writes and an import reads back
ALL_FIELDS: List[Dict[str, Any]] = [
    {"id": "name", "type": "short_text", "title": "Full name", "validations": {"required": True}},
    {"id": "bio", "type": "long_text", "title": "About you"},
    {"id": "mail", "type": "email", "title": "Email", "properties": {"why_we_ask": "To write back"}},
    {"id": "site", "type": "url", "title": "Website"},
    {"id": "phone", "type": "phone_number", "title": "Phone", "properties": {"why_we_ask": "To call you back"}},
    {"id": "age", "type": "number", "title": "Age"},
    {"id": "stars", "type": "rating", "title": "Stars"},
    {"id": "born", "type": "day", "title": "Born"},
    {"id": "start", "type": "date", "title": "Start date"},
    {"id": "arrival", "type": "time", "title": "Arrival"},
    {"id": "budget", "type": "currency", "title": "Budget", "properties": {"currencies": ["EUR", "GBP"]}},
    {"id": "stay", "type": "date_range", "title": "Stay"},
    {"id": "interests", "type": "tags", "title": "Interests"},
    {"id": "home", "type": "address", "title": "Home address"},
    {"id": "member", "type": "yes_no", "title": "Member"},
    {
        "id": "colour",
        "type": "dropdown",
        "title": "Favourite colour",
        "properties": {"choices": CHOICES, "allow_other_choice": True},
    },
    {
        "id": "colours",
        "type": "multiple_choice",
        "title": "Colours",
        "properties": {"choices": CHOICES, "allow_multiple_selection": True, "allow_other_choice": True},
    },
    {"id": "sign", "type": "signature", "title": "Signature"},
    {
        "id": "jobs",
        "type": "group",
        "title": "Jobs",
        "properties": {
            "repeat": {"min_items": 0, "max_items": 3, "item_label": "Job", "export_layout": "columns"},
            "fields": [
                {"id": "employer", "type": "short_text", "title": "Employer"},
                {"id": "since", "type": "day", "title": "Since"},
            ],
        },
    },
    {"id": "note", "type": "short_text", "title": "Staff note", "internal": True},
    {"id": "score", "type": "number", "title": "Staff score", "internal": True},
]

ADA = {
    "name": {"type": "text", "text": "Ada Lovelace"},
    "bio": {"type": "text", "text": "Wrote the first program.\nLoved maths."},
    "mail": {"type": "email", "email": "ada@example.org"},
    "site": {"type": "url", "url": "https://example.org/ada"},
    "phone": {"type": "phone_number", "phone_number": "+31 6 1234 5678"},
    "age": {"type": "number", "number": 36},
    "stars": {"type": "number", "number": 5},
    "born": {"type": "date", "date": "1815-12-10"},
    "start": {"type": "date", "date": "2026-10-01"},
    "arrival": {"type": "time", "time": "09:05"},
    "budget": {"type": "currency", "currency": {"code": "GBP", "amount": "1250.50"}},
    "stay": {"type": "date_range", "date_range": {"start": "2026-11-03", "end": "2026-11-07"}},
    "interests": {"type": "tags", "tags": ["maths", "gluten free"]},
    "home": {
        "type": "address",
        "address": {
            "street": "Keizersgracht",
            "house_number": "12",
            "house_number_addition": "A",
            "postcode": "1015 CS",
            "city": "Amsterdam",
            "country": "NL",
        },
    },
    "member": {"type": "boolean", "boolean": True},
    "colour": {"type": "choice", "choice": {"value": "c2"}},
    "colours": {"type": "choices", "choices": {"values": ["c1", "c2"], "other": "Teal"}},
    "sign": {"type": "signature", "signature": {"method": "typed", "name": "A. Lovelace"}},
    "jobs": {
        "type": "group",
        "items": [
            {"employer": {"type": "text", "text": "Babbage & Co"}, "since": {"type": "date", "date": "1840-01-02"}},
            {"employer": {"type": "text", "text": "Royal Society"}},
        ],
    },
}


async def submit(workspace, form, given: Dict[str, Any], hidden=None, user=testUser):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers=given, hidden_fields=hidden),
        user,
    )


def csv_bytes(rows: List[List[str]], separator: str = ",", bom: bool = False) -> bytes:
    out = io.StringIO(newline="")
    csv.writer(out, delimiter=separator, lineterminator="\r\n").writerows(rows)
    return (("﻿" if bom else "") + out.getvalue()).encode("utf-8")


def url(workspace, form, tail: str = "") -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/imports{tail}"


async def upload(client: AsyncClient, workspace, form, data: bytes, user=testUser, content_type="text/csv"):
    return await client.post(
        url(workspace, form), content=data, headers={"content-type": content_type}, cookies=_cookies(user)
    )


async def post(client: AsyncClient, workspace, form, import_id, tail, body=None, user=testUser):
    return await client.post(url(workspace, form, f"/{import_id}{tail}"), json=body or {}, cookies=_cookies(user))


async def get(client: AsyncClient, workspace, form, import_id, user=testUser):
    return await client.get(url(workspace, form, f"/{import_id}"), cookies=_cookies(user))


def service():
    return container.response_import_service()


async def run_job(import_id: str) -> str:
    return await service().run_job(import_id)


async def import_all(client, workspace, form, data, mapping=None, options=None, user=testUser, confirmed=True):
    """Upload, check, run and run the jobs; returns the final status body."""
    first = await upload(client, workspace, form, data, user=user)
    assert first.status_code == 201, first.text
    body = first.json()
    import_id = body["id"]
    chosen = mapping if mapping is not None else body["mapping"]
    request = {"mapping": chosen, "skipInvalidRows": bool((options or {}).get("skipInvalidRows")), "confirmedLawfulBasis": confirmed}
    queued = await post(client, workspace, form, import_id, "/run", request, user=user)
    assert queued.status_code == 202, queued.text
    await run_job(import_id)
    done = await get(client, workspace, form, import_id, user=user)
    assert done.status_code == 200, done.text
    return done.json()


async def stored_answers(workspace, form) -> List[Dict[str, Any]]:
    """The form's stored responses, decrypted, oldest first."""
    service_ = container.form_response_service()
    scope = await service_.scope(workspace.id, [str(form.form_id)])
    rows = await container.form_response_repo().export_batch(scope, None, after_id=None, limit=1000)
    out = []
    for row in rows:
        decrypted = service_.decrypt_form_response(workspace_id=workspace.id, response=row)
        out.append(decrypted)
    return out
