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


def hostnames(lines) -> set:
    """The host names that appear in log lines, parsed (not substring matched):
    every whitespace-separated token, as an address or as a bare name, lower
    case, with the punctuation a sentence puts around it removed."""
    from urllib.parse import urlsplit

    found = set()
    for line in lines:
        for token in line.split():
            token = token.strip(",.;:()[]{}'\"=").lower()
            host = urlsplit(token).hostname if "://" in token else token
            if host:
                found.add(host.rstrip("."))
    return found
