"""The credential of one queued action run.

The actions executor runs code that form creators wrote. The job key it holds
(``TEMPORAL_API_KEY``) is shared by every internal route, so on its own it must
not be enough to read a response. A run's data is served only against this
token: HMAC-SHA256, under a key derived from a secret only the backend holds
(never the executor, the queue or the database), of the four ids of the run.
The backend mints it when it queues the run and puts it in the job's arguments;
the executor sends it back with the ids. A holder of the job key who has no run
of its own to show cannot read anyone's answers, and a token for one run opens
no other.

It is not a password the respondent or a creator ever sees, and it opens only
the read of that run's data. It stays valid while its job's row exists (the
queue deletes finished action jobs after a week, a month when failed). The
key is derived from the respondent identity key with a label of its own, so
rotating that key (not implemented, docs/respondent-identity.md) also ends the
tokens of jobs still queued: those runs fail visibly.
"""

from __future__ import annotations

import hashlib
import hmac
import json

LABEL = b"bettercollected/action-run/token/v1"
HEADER = "run-token"


def _subkey() -> bytes:
    from backend.app.utils.respondent_identity import configured_key

    return hmac.new(configured_key(), LABEL, hashlib.sha256).digest()


def run_token(workspace_id, form_id, action_id, response_id) -> str:
    ids = [str(workspace_id), str(form_id), str(action_id), str(response_id)]
    return hmac.new(
        _subkey(), json.dumps(ids).encode(), hashlib.sha256
    ).hexdigest()


def is_valid_run_token(
    token: str, workspace_id, form_id, action_id, response_id
) -> bool:
    expected = run_token(workspace_id, form_id, action_id, response_id)
    return hmac.compare_digest((token or "").encode(), expected.encode())
