import pytest

from backend.app.container import container
from tests.app.open_formulieren.conftest import fixture_bytes

pytestmark = pytest.mark.asyncio


async def test_upload_a_fixture(client, workspace, test_user_cookies, import_on):
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/open-formulieren-imports",
        cookies=test_user_cookies,
        files={"file": ("export.zip", fixture_bytes("all-components.en.zip"), "application/zip")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    print(body["summary"], body["needsReview"], body["formId"])
    form = await container.form_repo().get_form_document_by_id(body["formId"])
    assert form is not None and form.title == "Sample: all components"
    again = await client.get(
        f"/api/v1/workspaces/{workspace.id}/open-formulieren-imports/{body['id']}",
        cookies=test_user_cookies,
    )
    assert again.status_code == 200 and again.json() == body
