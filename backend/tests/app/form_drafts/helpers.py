"""Builders shared by the draft tests. Everything here is synthetic."""

import json
import re
from typing import Any, Dict, List, Optional

from backend.app.container import container
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.registration.helpers import publish

ANSWERS = {
    "name": {"type": "text", "text": "Ada Example"},
    "story": {"type": "text", "text": "A synthetic story nobody should read."},
}
POSITION = {"pageId": "s1", "history": []}
TOKEN_IN_LINK = re.compile(r"#resume=([0-9a-f]{24}\.[A-Za-z0-9_-]{43})$")


def url(workspace, form, tail: str = "") -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/drafts{tail}"


def body(answers: Optional[Dict[str, Any]] = None, **extra) -> Dict[str, Any]:
    return {
        "answers": ANSWERS if answers is None else answers,
        "hiddenFields": {"source": "newsletter"},
        "position": POSITION,
        **extra,
    }


def cookies(user=testUser1) -> Dict[str, str]:
    return _cookies(user)


async def settings_of(workspace, form, **values) -> None:
    """Store settings on the workspace's link to the form, as they are."""
    repo = container.workspace_form_repo()
    link = await repo.get_workspace_form_in_workspace(
        workspace_id=workspace.id, query=str(form.form_id)
    )
    for key, value in values.items():
        setattr(link.settings, key, value)
    await repo.update(link.id, link)


async def drafting_form(workspace, **settings):
    """A published form that lets respondents save drafts."""
    form = await publish(workspace)
    await settings_of(workspace, form, allow_save_draft=True, **settings)
    return form


async def draft_rows() -> List[Any]:
    return await container.form_draft_repo().many()


def token_of(mail: Dict[str, Any]) -> str:
    found = TOKEN_IN_LINK.search(mail["json"]["link"])
    assert found, mail["json"]["link"]
    return found.group(1)


async def submit_over_http(
    client, workspace, form, answers=None, user_cookies=None, **fields
):
    """The normal submit route (multipart, as the respondent page sends it)."""
    payload = {"response": json.dumps({"answers": answers or {}}), **fields}
    return await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/response",
        data=payload,
        cookies=user_cookies,
    )


async def republish(workspace, form, title="A changed title", user=testUser):
    """A new published version of the form."""
    document = await container.form_repo().get_form_document_by_id(str(form.form_id))
    document.title = title
    await container.form_repo().save_form(document)
    return await container.workspace_form_service().publish_form(
        workspace.id, form.form_id, user
    )


def draft_ciphertexts(rows) -> str:
    """Everything stored for the drafts, as text (nothing of it may hold an
    answer, an address or a secret)."""
    return json.dumps([row.model_dump(mode="json") for row in rows])
