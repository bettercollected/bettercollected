"""Builders shared by the registration tests. Everything here is synthetic."""

from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.registration.service import (
    FormRegistrationUpdateDto,
    ServiceCreateDto,
    VariableMappingDto,
)
from tests.app.controllers.data import testUser

CHOICES = [
    {"id": "c1", "value": "Red"},
    {"id": "c2", "value": "Green"},
    {"id": "c3", "value": "Blue"},
]

FIELDS = [
    {"id": "name", "type": "short_text", "title": "Full name"},
    {"id": "story", "type": "long_text", "title": "Your story"},
    {
        "id": "mail",
        "type": "email",
        "title": "Email",
        "properties": {"why_we_ask": "To reply to you"},
    },
    {"id": "age", "type": "number", "title": "Age"},
    {"id": "agree", "type": "yes_no", "title": "Agree?"},
    {"id": "born", "type": "date", "title": "Birth date"},
    {
        "id": "colour",
        "type": "multiple_choice",
        "title": "Colour",
        "properties": {"choices": CHOICES},
    },
    {
        "id": "colours",
        "type": "multiple_choice",
        "title": "Colours",
        "properties": {"choices": CHOICES, "allow_multiple_selection": True},
    },
    {"id": "upload", "type": "file_upload", "title": "Document"},
    {
        "id": "people",
        "type": "group",
        "title": "People",
        "properties": {
            "repeat": {"minItems": 0, "maxItems": 5, "itemLabel": "Person"},
            "fields": [
                {"id": "pname", "type": "short_text", "title": "Person name"},
                {"id": "pyears", "type": "number", "title": "Years"},
            ],
        },
    },
    {"id": "intro", "type": "statement", "title": "Read this"},
]

ANSWERS = {
    "name": {"type": "text", "text": "Ada Example"},
    "story": {"type": "text", "text": "Synthetic story."},
    "mail": {"type": "email", "email": "ada@example.test"},
    "age": {"type": "number", "number": 36},
    "agree": {"type": "boolean", "boolean": True},
    "born": {"type": "date", "date": "1990-01-02"},
    "colour": {"type": "choice", "choice": {"value": "c2"}},
    "colours": {"type": "choices", "choices": {"values": ["c1", "c3"]}},
    "people": {
        "type": "group",
        "items": [
            {
                "pname": {"type": "text", "text": "Bo"},
                "pyears": {"type": "number", "number": 3},
            },
            {"pname": {"type": "text", "text": "Cy"}},
        ],
    },
}


async def publish(workspace, fields=None, hidden=None, user=testUser):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id,
        StandardForm(
            builder_version="v2",
            title="Registration test",
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


async def make_service(workspace, user=testUser, **overrides):
    values = dict(
        name="Case system",
        base_url="https://case.example.org/api/",
        auth="header",
        auth_name="Authorization",
        secret="Token s3cret-value",
        organisation_name="Example Org",
    )
    values.update(overrides)
    return await container.registration_service().create_service(
        workspace.id, ServiceCreateDto(**values), user
    )


async def configure(workspace, form, service, variables, user=testUser, **kwargs):
    request = FormRegistrationUpdateDto(
        enabled=kwargs.pop("enabled", True),
        service_id=service.id if service is not None else None,
        path=kwargs.pop("path", "intake"),
        variables=[
            VariableMappingDto(source=v) if isinstance(v, str) else v for v in variables
        ],
        **kwargs,
    )
    return await container.registration_service().put_form_registration(
        workspace.id, form.form_id, request, user
    )


async def submit(workspace, form, answers=None, hidden=None, user=testUser, **kwargs):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers=answers or ANSWERS, hidden_fields=hidden
        ),
        user,
        **kwargs,
    )
