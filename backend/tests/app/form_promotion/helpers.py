"""Builders shared by the form promotion tests. Everything here is synthetic."""

import copy
from types import SimpleNamespace

from common.ids import RecordId

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.email_action import EmailTemplate, FormEmailActionDocument
from backend.app.schemas.option_list import OptionListDocument, OptionListItem
from backend.app.schemas.registration import FormRegistrationDocument
from backend.app.schemas.webhook import FormWebhookDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import cookies

API = "/api/v1"
# a first-party-looking address in the test storage is not needed: Unsplash photos
# are first-party everywhere, anything else is dropped on a copy
UNSPLASH = "https://images.unsplash.com/photo-voorbeeld"
FOREIGN_IMAGE = "https://beelden.voorbeeld.example/a.png"


def spec_document(**changes) -> dict:
    """A small form: a text question with a pattern, a dropdown, a trust block."""
    document = {
        "specVersion": "1",
        "title": "Aanmelding",
        "language": "en",
        "pages": [
            {
                "id": "p1",
                "fields": [
                    {
                        "id": "naam",
                        "type": "short_text",
                        "title": "Naam",
                        "validations": {"required": True, "pattern": "^[a-z]+$"},
                    },
                    {
                        "id": "keuze",
                        "type": "dropdown",
                        "title": "Keuze",
                        "choices": [
                            {"id": "a", "value": "A"},
                            {"id": "b", "value": "B"},
                        ],
                    },
                ],
            }
        ],
        "trust": {
            "purpose": "Aanmelden",
            "retention": {"type": "days", "value": 90},
            "privacyPolicyUrl": "https://privacy.voorbeeld.example/beleid",
            "requireVerifiedIdentity": True,
        },
    }
    document.update(copy.deepcopy(changes))
    return document


def url(workspace, form_id, tail: str = "") -> str:
    return f"{API}/workspaces/{workspace.id}/forms/{form_id}{tail}"


async def make_member(workspace, user, *roles) -> None:
    """``user`` is a member of ``workspace`` holding ``roles`` (stored spellings)."""
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=user.id, roles=list(roles)
        )
    )


async def create_source(workspace, user=testUser, **changes):
    """A form made from a spec document: ``(form id, ETag)``."""
    form_id, _, etag = await container.form_spec_writer().create(
        workspace.id, spec_document(**changes), user
    )
    return form_id, etag


async def stored_spec(workspace, form_id):
    return await container.form_spec_writer().read(workspace.id, form_id)


async def option_list(workspace, name: str, *labels: str) -> OptionListDocument:
    """A list of the workspace (the name as typed, folded for its key)."""
    return await container.option_list_repo().create(
        OptionListDocument(
            workspace_id=workspace.id,
            name=name,
            name_key=name.casefold(),
            items=[OptionListItem(id=f"i{n}", label=label) for n, label in enumerate(labels)],
        )
    )


async def add_automations(workspace, form_id, webhooks=0, emails=0, registrations=0):
    """Rows that never move, with values the report must never show."""
    for n in range(webhooks):
        await container.form_webhook_repo().save(
            FormWebhookDocument(
                workspace_id=workspace.id,
                form_id=str(form_id),
                url_sealed=f"SEALED-URL-{n}",
                host=f"hooks{n}.voorbeeld.example",
                enabled=True,
                secret_sealed="SEALED-SECRET",
            )
        )
    for n in range(emails):
        template = EmailTemplate(subject="Hallo", body="Bedankt")
        await container.form_email_action_repo().save(
            FormEmailActionDocument(
                workspace_id=workspace.id,
                form_id=str(form_id),
                name=f"Mail {n}",
                en=template,
                nl=template,
                team_recipients=["ontvanger@voorbeeld.example"],
            )
        )
    for _ in range(registrations):
        await container.form_registration_repo().save(
            FormRegistrationDocument(
                workspace_id=workspace.id,
                form_id=str(form_id),
                enabled=True,
                path="zaken/voorbeeld",
            )
        )


def world_users():
    return SimpleNamespace(owner=testUser)


def body(target_workspace, **more) -> dict:
    return {"targetWorkspaceId": str(target_workspace.id), **more}


def headers(key: str = None) -> dict:
    return {"Idempotency-Key": key or str(RecordId())}


async def admin_of(workspace, user):
    await make_member(workspace, user, WorkspaceRoles.ADMIN.value)
    return user


def on(monkeypatch):
    monkeypatch.setattr(settings.form_promotion, "ENABLED", True)


__all__ = [name for name in dir() if not name.startswith("_")]
_ = cookies  # re-exported for the tests
