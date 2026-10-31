"""Builders shared by the email action tests. Everything here is synthetic."""

from common.ids import RecordId
from common.models.user import User

from backend.app.container import container
from backend.app.services.email_actions.service import (
    EmailActionCreateDto,
    TemplateDto,
)
from backend.app.services.webhooks.service import FieldDto
from backend.app.schemas.webhook import ActionCondition
from tests.app.controllers.data import testUser

OWNER = "owner@acme.example"
EN = TemplateDto(
    subject="New response to {{form_title}} from {{name}}",
    body="{{name}} sent a response.\n\n{{answers}}",
)
NL = TemplateDto(
    subject="Nieuwe inzending voor {{form_title}} van {{name}}",
    body="{{name}} stuurde een inzending.\n\n{{answers}}",
)


async def make_action(
    workspace, form, *, fields=("name", "age"), team=(OWNER,), respondent=None,
    user=testUser, condition=None, **overrides,
):
    values = dict(
        name="Notify the team",
        enabled=True,
        en=EN,
        nl=NL,
        fields=[FieldDto(source=f) if isinstance(f, str) else f for f in fields],
        team_recipients=list(team),
        respondent_copy=bool(respondent),
        condition=condition,
    )
    values.update(overrides)
    return await container.email_action_service().create_action(
        workspace.id, form.form_id, EmailActionCreateDto(**values), user
    )


def condition(*items, operator="AND"):
    return ActionCondition(operator=operator, conditions=list(items))


async def logs_of(form=None, action_type="email"):
    rows = await container.action_log_repo().many()
    return [
        r
        for r in rows
        if (form is None or r.form_id == form.form_id)
        and (action_type is None or r.action_type.value == action_type)
    ]


async def age(row, delta):
    """Make a log row older (its ``created_at`` column, which the sweep and the
    purge read)."""
    import datetime as dt  # noqa: F401

    from common.clock import utcnow
    from sqlalchemy import update

    repo = container.action_log_repo()
    table = repo.row.__table__
    async with repo._session() as session, session.begin():
        await session.execute(
            update(table).where(table.c.id == str(row.id)).values(created_at=utcnow() - delta)
        )


# the accounts the (faked) auth service knows, by id: ``verified`` adds to it
ACCOUNTS: dict = {}


def verified(address: str, *, proven: bool = True) -> User:
    """A signed-in respondent whose account email is ``address`` (``proven``:
    the session's email was verified at sign-in, by email code or single sign-on).
    The account exists at the faked auth service until it is removed from ``ACCOUNTS``."""
    user = User(
        id=str(RecordId()), sub=address, roles=["FORM_RESPONDER"], email_verified=True if proven else None
    )
    ACCOUNTS[user.id] = address
    return user


async def submit_as_owner_of_the_address(workspace, form, answers=None, **kwargs):
    """Submits as the person whose address the ``mail`` answer holds, signed in
    with a verified session (their account email is that address): the one case
    in which a copy is sent."""
    from tests.app.registration.helpers import ANSWERS, submit

    answers = answers or ANSWERS
    address = (answers.get("mail") or {}).get("email")
    user = kwargs.pop("user", None) or (verified(address) if address else testUser)
    return await submit(workspace, form, answers=answers, user=user, **kwargs)
