"""How deeply nested a JSON request body the RUNNING backend accepts, per route.

``json.loads`` of Python 3.11 (the deployed interpreter) is bounded by the
interpreter's recursion limit, which every Python frame on the stack already
uses, so the number depends on the route and the middleware stack, not only on
``json.loads``. This probe starts the real server (``python -m backend``,
uvicorn, as the image does), posts nested bodies with an ``Idempotency-Key`` (so
``request_hash`` reads the body first) and binary-searches the depth at which the
answer turns into a 500 (``RecursionError``). Re-run it when the backend image's
Python or its middleware stack changes, and set ``MAX_DEPTH`` in
``rust/bc-crypto/src/pyjson.rs`` from the result.

Not a test of the repository: copy it to ``backend/tests/app/controllers/test_zz_json_depth_probe.py`` and
run, from ``backend/`` in the 3.11 environment with the CI test environment and a
test database (``-n 1`` makes the suite create one)::

    uv run --python 3.11.12 python -m pytest tests/app/controllers/test_zz_json_depth_probe.py -n 1 -q

Results go to ``/tmp/depth_probe.out`` (xdist hides the output of a worker).
"""
import json
import os
import subprocess
import sys
import time

import httpx
import pytest

from tests.app.controllers.test_public_api import BASE, SPEC, _auth, _token
from tests.app.controllers.test_editor_ops_save import (  # noqa: F401
    _auth_service_users,
    _cookies,
    _etag,
    _ops_url,
    enabled,
    v2_form,
)


def _out(*parts):
    with open("/tmp/depth_probe.out", "a") as handle:
        handle.write(" ".join(str(p) for p in parts) + "\n")


def _body(kind: str, n: int) -> str:
    if kind == "array":
        return "[" * n + "]" * n
    if kind == "object":
        return '{"a":' * n + "1" + "}" * n
    return "[" * (n - 1) + "[]" + "]" * (n - 1)


async def test_depth(workspace, v2_form, test_user_cookies, client):
    token = await _token(workspace.id)
    etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
    env = dict(os.environ, PORT="18766", API_INTERNAL_PORT="0", API_EDITOR_OPS_SAVE_ENABLED="true")
    proc = subprocess.Popen([sys.executable, "-m", "backend"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = "http://127.0.0.1:18766"
        async with httpx.AsyncClient(timeout=60) as live:
            for _ in range(120):
                try:
                    await live.get(url + "/")
                    break
                except httpx.HTTPError:
                    time.sleep(1)
            created = await live.post(f"{url}{BASE}/forms", json=SPEC, headers=_auth(token))
            form_id = created.json()["formId"]
            counter = [0]
            routes = {
                "public create": lambda: (f"{url}{BASE}/forms", _auth(token), None),
                "public ops": lambda: (f"{url}{BASE}/forms/{form_id}/ops", _auth(token), None),
                "public publish": lambda: (f"{url}{BASE}/forms/{form_id}/publish", _auth(token), None),
                "editor ops": lambda: (f"{url}{_ops_url(workspace, v2_form.form_id)}", {"If-Match": etag}, test_user_cookies),
            }

            async def status(route, kind, n):
                counter[0] += 1
                target, headers, cookies = routes[route]()
                r = await live.post(
                    target,
                    content=_body(kind, n),
                    headers={**headers, "Idempotency-Key": f"probe-{counter[0]}", "Content-Type": "application/json"},
                    cookies=cookies,
                )
                return r.status_code

            for route in routes:
                _out("PROBE", route, "sanity shallow", await status(route, "array", 3), "deep", await status(route, "array", 2000))
                for kind in ("array", "object", "empty"):
                    lo, hi = 1, 1000
                    while lo < hi:
                        mid = (lo + hi + 1) // 2
                        if await status(route, kind, mid) != 500:
                            lo = mid
                        else:
                            hi = mid - 1
                    _out("PROBE", route, kind, "max depth not 500:", lo, "status there", await status(route, kind, lo), "next", await status(route, kind, lo + 1))
    finally:
        proc.terminate()
        proc.wait(timeout=20)
