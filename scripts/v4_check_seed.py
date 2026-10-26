"""Seeds fake data into a stack of the previous release (3.x), for scripts/v4-compose-check.sh.

It runs INSIDE that release's backend image (`docker compose run ... backend python
/seed.py`), so the documents are written by the release's own models and its own
response encryption, with the keyset the stack uses. Everything is invented:
two workspaces, three forms, six responses (answers and hidden fields encrypted the
way the application does it), and a few users in the auth database.

It prints counts only: never an id, an address, an answer or a key.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os

from beanie import PydanticObjectId
from pymongo import AsyncMongoClient

WORKSPACES = 2
FORMS_PER_WORKSPACE = (2, 1)
RESPONSES_PER_FORM = 2
USERS = 4
ANON_EMAIL = "dummy-respondent-{}-{}@example.test"
EXPIRATION = "2099-01-01T00:00:00.000Z"


async def main() -> None:
    from backend.app.handlers.database import init_db
    from backend.app.schemas.standard_form import FormDocument
    from backend.app.schemas.standard_form_response import FormResponseDocument
    from backend.app.schemas.workspace import WorkspaceDocument
    from backend.app.schemas.workspace_form import WorkspaceFormDocument
    from backend.app.utils.hash import hash_string
    from backend.config import settings
    from common.services.crypto_service import crypto_service

    client = AsyncMongoClient(os.environ["MONGO_URI"])
    await init_db(settings.mongo_settings.DB, client)

    forms = responses = 0
    for number in range(WORKSPACES):
        owner = f"dummy-owner-{number}"
        workspace = WorkspaceDocument(
            title=f"Dummy workspace {number}",
            workspace_name=f"dummy-workspace-{number}-{os.getpid()}",
            description="invented for the release acceptance check",
            owner_id=owner,
        )
        await workspace.save()
        for form_number in range(FORMS_PER_WORKSPACE[number]):
            form_id = f"dummy-form-{number}-{form_number}"
            await FormDocument(form_id=form_id, title=f"Dummy form {number}.{form_number}", description="invented").save()
            await WorkspaceFormDocument(workspace_id=workspace.id, form_id=form_id, user_id=owner).save()
            forms += 1
            for response_number in range(RESPONSES_PER_FORM):
                answers = json.dumps({"q1": {"text": f"invented answer {number}-{form_number}-{response_number}"}})
                hidden = json.dumps({"utm_source": "acceptance-check"})
                await FormResponseDocument(
                    response_id=f"dummy-response-{number}-{form_number}-{response_number}",
                    form_id=form_id,
                    provider="self",
                    answers=crypto_service.encrypt(workspace_id=str(workspace.id), form_id=form_id, data=answers),
                    hidden_fields=crypto_service.encrypt(workspace_id=str(workspace.id), form_id=form_id, data=hidden),
                    # the first response of each form was submitted anonymously: 3.x stored the MD5 of
                    # the signed-in address (the 4.1 identity pass converts it)
                    anonymous_identity=hash_string(ANON_EMAIL.format(number, form_number)) if response_number == 0 else None,
                    # one response is to be deleted on a date: 3.x scheduled that in Temporal, 4.1 on the job queue
                    **({"expiration": EXPIRATION, "expiration_type": "date"} if (number, form_number, response_number) == (0, 0, 0) else {}),
                ).save()
                responses += 1

    auth_db = client[os.environ.get("AUTH_MONGO_DB", "bettercollected_auth")]
    for number in range(USERS):
        await auth_db["users"].update_one(
            {"email": f"dummy-user-{number}@example.test"},
            {"$setOnInsert": {
                "first_name": "Dummy", "last_name": f"User {number}", "roles": [], "plan": "FREE",
                "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    print(f"seeded workspaces={WORKSPACES} forms={forms} responses={responses} users={USERS}")


if __name__ == "__main__":
    asyncio.run(main())
