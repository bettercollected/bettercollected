"""Builders shared by the reporting tests. Everything here is synthetic."""

import asyncio
import datetime as dt
from typing import Any, Dict, List, Optional

from common.ids import RecordId
from common.models.standard_form import StandardForm, StandardFormResponse

from backend.app.container import container
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import cookies

UTC = dt.timezone.utc


def choice_question(field_id, options, title="Pick", multiple=False, **properties):
    """A dropdown (or, with ``multiple``, a checkboxes question) whose options
    are ``{id: label}``."""
    return {
        "id": field_id,
        "type": "multiple_choice" if multiple else "dropdown",
        "title": title,
        "properties": {
            "choices": [{"id": i, "value": label, "label": label} for i, label in options.items()],
            "allow_multiple_selection": multiple,
            **properties,
        },
    }


def simple_question(field_id, kind, title="Question", **properties):
    return {"id": field_id, "type": kind, "title": title, "properties": properties}


def survey_fields() -> List[Dict[str, Any]]:
    """The questions most tests run over: a choice, checkboxes, a rating, a
    number, yes/no, a date, a currency and one text question."""
    return [
        choice_question("dept", {"care": "Care", "it": "IT", "hr": "HR"}, "Department", allow_other_choice=True),
        choice_question("tools", {"mail": "Mail", "chat": "Chat", "wiki": "Wiki"}, "Tools", multiple=True),
        simple_question("score", "rating", "Score"),
        simple_question("age", "number", "Age"),
        simple_question("remote", "yes_no", "Remote"),
        simple_question("start", "date", "Start"),
        simple_question("fee", "currency", "Fee", currencies=["EUR"]),
        simple_question("why", "short_text", "Why"),
    ]


def page(fields) -> List[Dict[str, Any]]:
    return [{"id": "s1", "type": "slide", "index": 0, "properties": {"fields": fields}}]


async def make_form(workspace, fields, user=testUser, title="Survey", publish=True, **more):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id,
        StandardForm(builder_version="v2", title=title, fields=page(fields), **more),
        user,
    )
    if publish:
        await service.publish_form(workspace.id, form.form_id, user)
    return form


async def republish(workspace, form, fields, user=testUser):
    """Change the draft's questions and publish it again: the next version."""
    service = container.workspace_form_service()
    await service.update_form(
        workspace.id,
        form.form_id,
        StandardForm(builder_version="v2", title=form.title, fields=page(fields)),
        user,
    )
    await service.publish_form(workspace.id, form.form_id, user)


def answer_choice(option_id=None, other=None):
    block = {}
    if option_id is not None:
        block["value"] = option_id
    if other is not None:
        block["other"] = other
    return {"type": "choice", "choice": block}


def answer_choices(*option_ids, other=None):
    block = {"values": list(option_ids)}
    if other is not None:
        block["other"] = other
    return {"type": "choices", "choices": block}


def answer_number(value):
    return {"type": "number", "number": value}


def answer_bool(value):
    return {"type": "boolean", "boolean": value}


def answer_date(day):
    return {"type": "date", "date": day}


def answer_currency(amount, code="EUR"):
    return {"type": "currency", "currency": {"code": code, "amount": amount}}


def answer_text(text):
    return {"type": "text", "text": text}


async def add_response(
    workspace,
    form,
    answers: Dict[str, Any],
    version: Optional[int] = 1,
    at: Optional[dt.datetime] = None,
    identified: bool = False,
    ending_id: Optional[str] = None,
    document: bool = False,
):
    """Store a response as a submission does (encrypted answers), with the
    given version and submission time; the id of the stored response."""
    response = StandardFormResponse(
        answers=answers,
        form_version=version,
        dataOwnerIdentifier=f"person-{len(answers)}@example.org" if identified else None,
        ending_id=ending_id,
        response_id=str(RecordId()),
    )
    stored = await container.form_response_repo().save_form_response(
        form_id=form.form_id,
        response=response,
        workspace_id=workspace.id,
        submitted_at=at,
    )
    return stored if document else str(stored.id)


async def add_many(workspace, form, items: List[Dict[str, Any]], concurrency: int = 25) -> List[str]:
    """``add_response`` for each of ``items`` (keyword arguments), a few at a time."""
    ids: List[str] = []
    for start in range(0, len(items), concurrency):
        ids.extend(
            await asyncio.gather(
                *(add_response(workspace, form, **item) for item in items[start : start + concurrency])
            )
        )
    return ids


def report_url(workspace, form, tail="query") -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/report/{tail}"


def definition(*cards, **changes) -> Dict[str, Any]:
    body: Dict[str, Any] = {"v": 1, "cards": list(cards)}
    body.update(changes)
    return body


def card(card_id="c1", kind="table", dimension=None, measures=None, **extra) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "id": card_id,
        "kind": kind,
        "measures": measures if measures is not None else [{"agg": "count"}],
    }
    if dimension is not None:
        result["dimension"] = dimension if isinstance(dimension, dict) else {"field": dimension}
    result.update(extra)
    return result


async def query(client, workspace, form, body, user=testUser, tail="query", method="post"):
    send = getattr(client, method)
    kwargs = {"json": body} if method == "post" else {}
    return await send(report_url(workspace, form, tail), cookies=cookies(user), **kwargs)


def groups_of(result: Dict[str, Any], card_id="c1") -> Dict[str, Any]:
    """{group key: group} of one card of a query result."""
    found = next(c for c in result["cards"] if c["id"] == card_id)
    return {g["key"]: g for g in found["groups"]}


def card_of(result: Dict[str, Any], card_id="c1") -> Dict[str, Any]:
    return next(c for c in result["cards"] if c["id"] == card_id)
