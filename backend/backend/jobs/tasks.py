"""Job bodies. They call the same service methods the Temporal workers reach
today over HTTP (``/auth/user``, ``/temporal/delete/submissions/…``) — in
process, no HTTP hop, no API key. ``run_action`` is deliberately *not* defined
here: the backend only defers it by name; the actions-executor process owns
the body (temporal/actions-executor/procrastinate_worker.py) and is the only
consumer of the ``actions`` queue.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import jwt
from procrastinate import RetryStrategy

from backend.app.models.dataclasses.user_tokens import UserTokens
from backend.app.services.user_service import get_user_from_token
from backend.config import settings
from backend.jobs.app import ACTIONS_QUEUE, DEFAULT_QUEUE, app

RUN_ACTION = "run_action"


def _container():
    from backend.app.container import container  # at call time: importing app boots it

    return container


@app.task(
    name="delete_user",
    queue=DEFAULT_QUEUE,
    retry=RetryStrategy(max_attempts=4, exponential_wait=2),
)
async def delete_user(encrypted_tokens: str, user_id: str) -> str:
    """The user's workspaces, forms, integrations and auth record — what the
    Temporal `delete_user` activity did via DELETE /auth/user with the user's
    own tokens; the tokens travel encrypted exactly as before."""
    container = _container()
    tokens = UserTokens(**json.loads(container.crypto().decrypt(encrypted_tokens)))
    user = get_user_from_token(tokens.access_token)
    await container.auth_service().delete_user(user=user)
    claims = jwt.decode(
        tokens.refresh_token,
        key=settings.auth_settings.JWT_SECRET,
        algorithms=["HS256"],
    )
    await container.blacklisted_refresh_token_repo().add(
        token=tokens.refresh_token, expiry=claims.get("exp")
    )
    return "User Deleted Successfully"


@app.task(
    name="delete_response",
    queue=DEFAULT_QUEUE,
    retry=RetryStrategy(max_attempts=4, exponential_wait=2),
)
async def delete_response(response_id: str) -> str:
    """Scheduled at the response's expiration (`schedule_at`); one-shot, so
    unlike the Temporal path there is no schedule left to delete afterwards."""
    await _container().form_response_service().delete_response(response_id=response_id)
    return response_id


def run_action_deferrer(queueing_lock: str):
    """Defer ``run_action`` to the actions queue without importing its body."""
    return app.configure_task(
        name=RUN_ACTION, queue=ACTIONS_QUEUE, queueing_lock=queueing_lock
    )
