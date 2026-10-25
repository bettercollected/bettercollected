"""Internal routes for the admin task runner (``backend.admin.tasks``).

Only the runner calls them: it presents ``ADMIN_TASKS_API_KEY`` in
``X-Admin-Tasks-Key``; no session, no other key is accepted. Unset key: 503
(fail closed). They answer on the backend's internal listener only
(``API_INTERNAL_PORT``, never published; ``services/internal_routes.py``):
anywhere else, or through a proxy, they are a 404 before the key is checked. Each route does one narrow thing, and decides itself what it
may do: the runner names an account, never a decision.

* ``GET  /internal/admin-tasks/case-duplicate-accounts``: the groups of
  accounts whose emails differ only in case, with the forms count and the
  decision of each (ids only).
* ``POST /internal/admin-tasks/case-duplicate-accounts/{user_id}/drop``:
  re-evaluates the account's group and, only if the rules still drop it,
  starts the product's account deletion
  (``services/case_duplicate_accounts.py``).
"""

import hmac
from http import HTTPStatus

from classy_fastapi import Routable, get, post
from fastapi import Depends, Request
from loguru import logger

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.router import router
from backend.app.services.internal_routes import require_internal_listener
from backend.config import settings

KEY_HEADER = "X-Admin-Tasks-Key"


def require_admin_tasks_key(request: Request) -> None:
    # the internal listener only (404 otherwise), before the key is looked at
    require_internal_listener(request)
    expected = (settings.ADMIN_TASKS_API_KEY or "").strip()
    if not expected:
        logger.error("Refused an admin task request: ADMIN_TASKS_API_KEY is not set.")
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            content="The admin task key (ADMIN_TASKS_API_KEY) is not configured.",
        )
    given = (request.headers.get(KEY_HEADER) or "").encode()
    if not hmac.compare_digest(given, expected.encode()):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            content="You are not allowed to perform this action.",
        )


def _object_id(user_id: str) -> str:
    if len(user_id) != 24 or any(c not in "0123456789abcdef" for c in user_id):
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, content="Invalid id.")
    return user_id


@router(
    prefix="/internal/admin-tasks",
    tags=["Admin tasks (internal)"],
    dependencies=[Depends(require_admin_tasks_key)],
    include_in_schema=False,
)
class AdminTasksRouter(Routable):
    def __init__(
        self, case_duplicates=container.case_duplicate_accounts(), *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.case_duplicates = case_duplicates

    @get("/case-duplicate-accounts")
    async def case_duplicate_accounts(self):
        groups = await self.case_duplicates.plan()
        return {
            "groups": [[account.as_dict() for account in group] for group in groups]
        }

    @post("/case-duplicate-accounts/{user_id}/drop")
    async def drop_case_duplicate_account(self, user_id: str):
        status = await self.case_duplicates.drop(_object_id(user_id))
        return {"status": status}
