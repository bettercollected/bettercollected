"""Builders shared by the option source tests. Everything here is synthetic."""

from common.models.standard_form import StandardForm
from common.models.user import User
from common.ids import RecordId

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.option_lists.service import ItemDto, OptionListCreateDto
from backend.app.services.option_sources import share_token
from backend.app.services.option_sources.checks import shared_ids
from tests.app.controllers.data import invited_user, testUser

CITIES = [
    ("Amsterdam", "Netherlands"),
    ("Utrecht", "Netherlands"),
    ("Berlin", "Germany"),
    ("Hamburg", "Germany"),
    ("Anywhere", None),
]


async def make_list(
    workspace, name="Cities", items=CITIES, user=testUser, order="manual"
):
    return await container.option_list_service().create_list(
        workspace.id,
        OptionListCreateDto(
            name=name,
            order=order,
            items=[ItemDto(label=label, group=group) for label, group in items],
        ),
        user,
    )


def ids_of(listing) -> dict:
    """{label: id} of a list DTO."""
    return {item.label: item.id for item in listing.items}


def question(field_id, kind="dropdown", title="Pick", source=None, **properties):
    props = dict(properties)
    if source is not None:
        props["option_source"] = source
    return {"id": field_id, "type": kind, "title": title, "properties": props}


async def publish(workspace, fields, user=testUser, title="Sources test"):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id,
        StandardForm(
            builder_version="v2",
            title=title,
            fields=[
                {
                    "id": "s1",
                    "type": "slide",
                    "index": 0,
                    "properties": {"fields": fields},
                }
            ],
        ),
        user,
    )
    await service.publish_form(workspace.id, form.form_id, user)
    return form


async def page_token(workspace, form):
    """The notice token a respondent's page of ``form`` gets now (the form
    fetch of the published version)."""
    latest = await container.form_service().get_latest_version_of_form(form.form_id)
    return share_token.issue_token(
        workspace_id=workspace.id,
        form_id=form.form_id,
        question_ids=shared_ids(latest),
    )


async def submit(workspace, form, answers, user=testUser, **kwargs):
    """A submission from a page loaded just now (its notice token is what the
    form fetch hands out); pass ``share_notice_token`` to send another one."""
    if "share_notice_token" not in kwargs:
        kwargs["share_notice_token"] = await page_token(workspace, form)
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers=answers),
        user,
        **kwargs,
    )


def choice(option_id, **extra):
    return {"type": "choice", "choice": {"value": option_id, **extra}}


def choices(*option_ids, **extra):
    return {"type": "choices", "choices": {"values": list(option_ids), **extra}}


def text(value):
    return {"type": "text", "text": value}


def outsider() -> User:
    return User(
        id=str(RecordId()), sub="outsider@elsewhere.example", roles=["FORM_RESPONDER"]
    )


def member(role_user=invited_user) -> User:
    return role_user


async def stored_answers(workspace, form):
    """The decrypted answers of every stored response of the form."""
    scope = await container.form_response_service().scope(workspace.id, [form.form_id])
    found = []
    for row in await container.form_response_repo().list_by_form_id(scope):
        decrypted = container.form_response_service().decrypt_form_response(
            workspace_id=workspace.id, response=row
        )
        found.append(decrypted.answers)
    return found
