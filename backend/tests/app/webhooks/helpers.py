"""Builders shared by the webhook tests. Everything here is synthetic."""

from backend.app.container import container
from backend.app.services.webhooks.service import FieldDto, WebhookCreateDto
from tests.app.controllers.data import testUser

URL = "https://case.example.org/hooks/intake"


async def make_webhook(workspace, form, fields=("name", "age"), user=testUser, **overrides):
    values = dict(
        url=URL,
        fields=[FieldDto(source=f) if isinstance(f, str) else f for f in fields],
        enabled=True,
    )
    values.update(overrides)
    return await container.webhook_service().create_webhook(
        workspace.id, form.form_id, WebhookCreateDto(**values), user
    )


async def logs_of(form=None):
    rows = await container.action_log_repo().many()
    return [r for r in rows if form is None or r.form_id == form.form_id]
