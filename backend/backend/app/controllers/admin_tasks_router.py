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
``{"code": "auth_unreachable" | "auth_misconfigured" | "auth_refused" |
"auth_error", "status": <auth's status or null>}`` (never auth's body); when
the account deletion cannot be started, the drop answers 502 with
``deletion_unavailable``. 503 is the API's own missing key and nothing else
(a 503 from inside a route is answered 500), so the runner can tell these
apart.
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
from backend.app.services.case_duplicate_accounts import UpstreamFailed
from common.exceptions.http import HTTPException as CommonHTTPException
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


async def _answer(route: str, call):
    """The route's reply; what it depends on failing is a 502 with a code and
    a status (never a body, an id or an email), and a 503 raised inside it
    (a dependency's, not the key's) becomes a 500, so the runner's
    ``backend_key_missing`` only ever means the key is unset."""
    try:
        return await call()
    except UpstreamFailed as error:
        logger.warning(
            "Admin task route {}: {} (status {}).", route, error.code, error.status
        )
        return JSONResponse(
            status_code=HTTPStatus.BAD_GATEWAY,
            content={"code": error.code, "status": error.status},
        )
    except (HTTPException, CommonHTTPException) as error:
        if error.status_code != HTTPStatus.SERVICE_UNAVAILABLE:
            raise
        logger.warning("Admin task route {}: a dependency answered 503.", route)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={"code": "backend_error", "status": error.status_code},
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
        async def plan():
            groups = await self.case_duplicates.plan()
            return {
                "groups": [[account.as_dict() for account in group] for group in groups]
            }

        return await _answer("case-duplicate-accounts", plan)

    @post("/case-duplicate-accounts/{user_id}/drop")
    async def drop_case_duplicate_account(self, user_id: str):
        account_id = _object_id(user_id)

        async def drop():
            return {"status": await self.case_duplicates.drop(account_id)}

        return await _answer("case-duplicate-accounts drop", drop)
