"""Internal routes for the admin task runner (``backend.admin.tasks``).

Only the runner calls them: it presents ``ADMIN_TASKS_API_KEY`` in
``X-Admin-Tasks-Key``; no session, no other key is accepted. Unset key: 503
(fail closed). Each route does one narrow thing, and decides itself what it
may do: the runner names an account, never a decision.

* ``GET  /internal/admin-tasks/case-duplicate-accounts``: the groups of
  accounts whose emails differ only in case, with the forms count and the
  decision of each (ids only).
* ``POST /internal/admin-tasks/case-duplicate-accounts/{user_id}/drop``:
  re-evaluates the account's group and, only if the rules still drop it,
  starts the product's account deletion
  (``services/case_duplicate_accounts.py``).

When the API's call to the auth service fails, both answer 502 with
``{"code": "auth_unreachable" | "auth_refused" | "auth_error", "status":
<auth's status or null>}`` (never auth's body), so the runner can tell an
auth problem from the API's own 503 (no key) and 403 (wrong key).
"""

import hmac
from http import HTTPStatus

from classy_fastapi import Routable, get, post
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.router import router
from backend.app.services.case_duplicate_accounts import AuthCallFailed
from backend.config import settings

KEY_HEADER = "X-Admin-Tasks-Key"


def require_admin_tasks_key(request: Request) -> None:
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


def _auth_failed(route: str, error: AuthCallFailed) -> JSONResponse:
    # code and status only: never auth's body, an id or an email
    logger.warning(
        "Admin task route {}: the auth service call failed ({}, status {}).",
        route,
        error.code,
        error.status,
    )
    return JSONResponse(
        status_code=HTTPStatus.BAD_GATEWAY,
        content={"code": error.code, "status": error.status},
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
        try:
            groups = await self.case_duplicates.plan()
        except AuthCallFailed as error:
            return _auth_failed("case-duplicate-accounts", error)
        return {
            "groups": [[account.as_dict() for account in group] for group in groups]
        }

    @post("/case-duplicate-accounts/{user_id}/drop")
    async def drop_case_duplicate_account(self, user_id: str):
        try:
            status = await self.case_duplicates.drop(_object_id(user_id))
        except AuthCallFailed as error:
            return _auth_failed("case-duplicate-accounts drop", error)
        return {"status": status}
