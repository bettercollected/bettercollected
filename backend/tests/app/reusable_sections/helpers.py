"""Builders shared by the reusable section tests. Everything here is synthetic."""

import copy
from typing import Any, Dict, List

from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.services.reusable_sections.service import SectionCreateDto
from tests.app.controllers.data import testUser


def q(field_id: str, kind: str = "short_text", title: str = "Question", **props) -> Dict[str, Any]:
    """A question as the builder holds it."""
    field: Dict[str, Any] = {"id": field_id, "type": kind, "title": title, "properties": {"fields": [], **props}}
    return field


def validations(field: Dict[str, Any], **values) -> Dict[str, Any]:
    field["validations"] = values
    return field


def cond(field_id: str, comparison: str = "IS_NOT_EMPTY", value: Any = None) -> Dict[str, Any]:
    return {"fieldId": field_id, "comparison": comparison, "value": value}


def show_if(*conditions) -> Dict[str, Any]:
    return {"action": "SHOW", "operator": "AND", "conditions": list(conditions)}


def rich(*nodes) -> Dict[str, Any]:
    return {"type": "doc", "content": [{"type": "paragraph", "content": list(nodes)}]}


def pipe(key: str, kind: str = "field") -> Dict[str, Any]:
    return {"type": "answerPipe", "attrs": {"kind": kind, "pipeKey": key, "label": key}}


def applicant_fields() -> List[Dict[str, Any]]:
    """Questions that point at each other in every way the remap must follow."""
    return [
        q("name", title=rich({"type": "text", "text": "Name"})),
        validations(q("age", "number", "Age", logic=show_if(cond("name"))), required=True),
        q(
            "kind",
            "dropdown",
            "Kind",
            choices=[{"id": "k1", "value": "one"}, {"id": "k2", "value": "two"}],
        ),
        q(
            "extra",
            "multiple_choice",
            "Extra for {{field:name|you}}",
            choices=[
                {"id": "e1", "value": "a", "logic": show_if(cond("name"))},
                {"id": "e2", "value": "b"},
            ],
            optionFilter={"fieldId": "kind", "mapping": [{"when": "k1", "show": ["e1"]}]},
        ),
        q(
            "limit",
            "number",
            "Limit",
            rules=[
                {
                    "id": "r1",
                    "when": {"conditions": [cond("age", "GREATER_THAN", 17)]},
                    "then": {"required": True, "title": "Limit for {{field:name}}"},
                },
                {
                    "id": "r2",
                    "when": {"expression": {">": [{"var": "age"}, 1]}},
                    "then": {"setValue": {"expression": {"+": [{"var": "age"}, 1]}}},
                },
            ],
        ),
        q(
            "people",
            "group",
            "People",
            fields=[
                q("who", title="Who"),
                q("role", title="Role", logic=show_if(cond("who"))),
            ],
            repeat={"minItems": 1, "maxItems": 3, "itemTitle": "Person {{field:who}}"},
        ),
        q("total", "calculated", "Total", expression={"+": [{"var": "age"}, {"var": "limit"}]}),
        q("summary", "text", rich(pipe("name"), pipe("people:count", "group"))),
    ]


def applicant_containers() -> List[Dict[str, Any]]:
    return [{"id": "box", "type": "panel", "title": "Applicant", "fields": ["name", "age"]}]


async def make_section(workspace, name="Applicant", fields=None, containers=None, user=testUser):
    return await container.reusable_section_service().create_section(
        workspace.id,
        SectionCreateDto(
            name=name,
            description="A person",
            fields=copy.deepcopy(fields if fields is not None else applicant_fields()),
            containers=copy.deepcopy(
                containers if containers is not None else applicant_containers()
            ),
        ),
        user,
    )


async def form_with_page(workspace, fields=None, user=testUser) -> Any:
    service = container.workspace_form_service()
    return await service.create_form(
        workspace.id,
        StandardForm(
            builder_version="v2",
            title="Sections test",
            fields=[
                {
                    "id": "s1",
                    "type": "slide",
                    "index": 0,
                    "properties": {"fields": fields or [q("intro", title="Intro")]},
                }
            ],
        ),
        user,
    )
