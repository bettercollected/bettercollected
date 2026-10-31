"""Builders shared by the export tests. Everything here is synthetic."""

import csv
import io
import zipfile
from typing import List

from common.models.standard_form import StandardForm
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from tests.app.controllers.data import testUser
from tests.app.controllers.test_permission_matrix import _cookies

CHOICES = [
    {"id": "c1", "value": "Red"},
    {"id": "c2", "value": "Green"},
    {"id": "c3", "value": "Blue"},
]

FIELDS = [
    {"id": "name", "type": "short_text", "title": "Full name"},
    {
        "id": "phone",
        "type": "phone_number",
        "title": "Phone",
        "properties": {"why_we_ask": "To call you back"},
    },
    {"id": "age", "type": "number", "title": "Age"},
    {
        "id": "colours",
        "type": "multiple_choice",
        "title": "Colours",
        "properties": {"choices": CHOICES, "allow_multiple_selection": True},
    },
]

GROUP_FIELDS = FIELDS + [
    {
        "id": "jobs",
        "type": "group",
        "title": "Jobs",
        "properties": {
            "repeat": {
                "min_items": 0,
                "max_items": 6,
                "item_label": "Job",
                "export_layout": "rows",
            },
            "fields": [
                {"id": "employer", "type": "short_text", "title": "Employer"},
            ],
        },
    },
]


async def publish(workspace, fields=None, hidden=None, user=testUser, title="Export test"):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id,
        StandardForm(
            builder_version="v2",
            title=title,
            hidden_fields=hidden,
            fields=[
                {
                    "id": "s1",
                    "type": "slide",
                    "index": 0,
                    "properties": {"fields": fields or FIELDS},
                }
            ],
        ),
        user,
    )
    await service.publish_form(workspace.id, form.form_id, user)
    return form


def answers(name: str, phone: str = "+31 6 1234", age: int = 30, colours=("c1", "c3")) -> dict:
    return {
        "name": {"type": "text", "text": name},
        "phone": {"type": "phone_number", "phone_number": phone},
        "age": {"type": "number", "number": age},
        "colours": {"type": "choices", "choices": {"values": list(colours)}},
    }


async def submit(workspace, form, given=None, hidden=None, user=testUser):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers=given or answers("Ada"), hidden_fields=hidden
        ),
        user,
    )


async def submit_many(workspace, form, count: int, prefix: str = "Person") -> None:
    for number in range(count):
        await submit(workspace, form, answers(f"{prefix} {number}", age=20 + number))


def url(workspace, form, tail: str = "") -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/exports{tail}"


async def start(client: AsyncClient, workspace, form, body=None, user=testUser):
    return await client.post(
        url(workspace, form), json=body or {}, cookies=_cookies(user)
    )


def text(response) -> str:
    return response.content.decode("utf-8").removeprefix("﻿")


def rows(response) -> List[List[str]]:
    return list(csv.reader(io.StringIO(text(response), newline="")))


def zip_rows(content: bytes) -> dict:
    archive = zipfile.ZipFile(io.BytesIO(content))
    return {
        name: list(
            csv.reader(
                io.StringIO(archive.read(name).decode("utf-8").removeprefix("﻿"), newline="")
            )
        )
        for name in archive.namelist()
    }
