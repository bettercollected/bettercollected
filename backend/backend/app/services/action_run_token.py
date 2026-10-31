"""The credential of one queued action run.

The actions executor runs code that form creators wrote. The job key it holds
(``TEMPORAL_API_KEY``) is shared by every internal route, so on its own it must
not be enough to read a response. A run's data is served only against this
token, and only while that run is in flight:

* **Signed by the backend.** ``<expiry>.<HMAC-SHA256>`` of the run's four ids
  and the expiry, under a key derived from a secret only the backend holds
  (never the executor, the queue or the database). The executor cannot forge or
  extend one.
* **Expires.** ``TTL_SECONDS`` after the run was queued: a run that waited longer
  than that (an executor that was down for a day) is skipped, not run late.
* **Bound to its job.** The route also finds the job in the ``actions`` queue,
  ``doing`` and with exactly these ids and this token (``job_matches``): a token
  read from the queue after the run finished, or for a run not started, opens
  nothing.

This narrows what a holder of the job key and the executor's queue access can
read; it does not stop code running inside the executor from marking a queued
row ``doing`` (its role may update the ``actions`` rows). Isolating the executor
from the queue's other rows and from the process's own secrets is the executor
track's work; keep form actions off until it is done. The key is derived
from the respondent identity key with a label of its own, so rotating that key
(not implemented, docs/respondent-identity.md) also ends the tokens of jobs still
queued: those runs fail visibly.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Iterable, Optional

LABEL = b"bettercollected/action-run/token/v2"
HEADER = "run-token"
TTL_SECONDS = 24 * 3600
VALID, EXPIRED, INVALID = "valid", "expired", "invalid"


def _subkey() -> bytes:
    from backend.app.utils.respondent_identity import configured_key

    return hmac.new(configured_key(), LABEL, hashlib.sha256).digest()


def run_lock(action_id, form_id, response_id) -> str:
    """The queueing lock of a run: one run of an action on a response at a time.
    The executor's role may only write locks that start with ``action_``."""
    return "action_" + str(action_id) + str(form_id) + str(response_id)


def _sign(ids: Iterable, expiry: int) -> str:
    message = json.dumps([*map(str, ids), expiry]).encode()
    return hmac.new(_subkey(), message, hashlib.sha256).hexdigest()


def run_token(
    workspace_id, form_id, action_id, response_id, now: Optional[float] = None
) -> str:
    expiry = int((time.time() if now is None else now) + TTL_SECONDS)
    ids = (workspace_id, form_id, action_id, response_id)
    return f"{expiry}.{_sign(ids, expiry)}"


def check_run_token(
    token: str,
    workspace_id,
    form_id,
    action_id,
    response_id,
    now: Optional[float] = None,
) -> str:
    """``VALID``, ``EXPIRED`` (signed by us, past its time) or ``INVALID``."""
    expiry_text, _, signature = (token or "").partition(".")
    if not expiry_text.isdigit() or not signature:
        return INVALID
    expiry = int(expiry_text)
    ids = (workspace_id, form_id, action_id, response_id)
    if not hmac.compare_digest(signature.encode(), _sign(ids, expiry).encode()):
        return INVALID
    return EXPIRED if (time.time() if now is None else now) > expiry else VALID


def job_matches(job, token: str, workspace_id, form_id, action_id, response_id) -> bool:
    """Whether a queue row is this run's: ``run_action`` on the ``actions``
    queue with exactly these ids and this token in its arguments."""
    args = getattr(job, "task_kwargs", None) or {}
    wanted = {
        "action_id": str(action_id),
        "form_id": str(form_id),
        "response_id": str(response_id),
        "workspace_id": str(workspace_id),
    }
    return (
        getattr(job, "task_name", None) == "run_action"
        and getattr(job, "queue", None) == "actions"
        and all(str(args.get(key)) == value for key, value in wanted.items())
        and hmac.compare_digest(str(args.get("run_token", "")).encode(), token.encode())
    )
