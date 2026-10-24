"""An import running as a background task in the API process never ends with
an exception nobody retrieves: asyncio would log it later, at garbage
collection, with whatever the traceback holds, and the import would keep its
workspace's import slot. An error outside the pipeline's own handling fails
the import with code "failed" and removes its empty draft."""

import asyncio
import gc

import pytest

from backend.app.container import container
from backend.app.schemas.form_import import ImportStatus
from tests.app.pdf_import import documents
from tests.app.pdf_import.test_api import _gone, limits, upload, url
from tests.app.pdf_import.test_api import store  # noqa: F401 — fixture

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def loop_errors():
    """What reaches the event loop's exception handler meanwhile."""
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()
    seen = []
    loop.set_exception_handler(lambda _loop, context: seen.append(context))
    yield seen
    loop.set_exception_handler(previous)


@pytest.fixture
def sandbox_gone_and_give_up_crashes():
    """The sandbox is unreachable with no retries left, and failing the import
    for it raises (as when the database drops at that moment)."""
    import backend.app.services.pdf_import_service as module

    settings_, pipeline = limits(), container.pdf_import_pipeline()
    socket, delays = settings_.SANDBOX_SOCKET, module.RETRY_DELAYS_S
    settings_.SANDBOX_SOCKET = "/nonexistent/sandbox.sock"
    module.RETRY_DELAYS_S = ()

    async def give_up(import_id):
        raise RuntimeError("unexpected")

    pipeline.give_up = give_up
    yield
    del pipeline.give_up  # back to the class's
    settings_.SANDBOX_SOCKET, module.RETRY_DELAYS_S = socket, delays


async def test_an_unexpected_error_fails_the_import_and_is_never_left_unretrieved(
    client,
    workspace,
    test_user_cookies,
    store,  # noqa: F811
    loop_errors,
    sandbox_gone_and_give_up_crashes,
):
    from loguru import logger

    service = container.pdf_import_service()
    lines = []
    # diagnose=False as in production (handlers/__init__.py)
    sink = logger.add(lambda m: lines.append(str(m)), level="DEBUG", diagnose=False)
    try:
        response = await upload(
            client, workspace, test_user_cookies, documents.text_pdf(), "Quokka.pdf"
        )
        assert response.status_code == 202, response.text
        body = response.json()

        # Wait for the import's task without retrieving its result (as the
        # dispatcher does: nothing awaits it), then let it be collected.
        running = set(service._running)
        assert running
        await asyncio.wait(running)
        del running
        gc.collect()
        await asyncio.sleep(0)
    finally:
        logger.remove(sink)

    assert [c.get("message") for c in loop_errors] == []
    logged = "\n".join(lines)
    assert f"form import {body['id']} could not run" in logged
    assert "Quokka" not in logged
    done = await client.get(f"{url(workspace)}/{body['id']}", cookies=test_user_cookies)
    assert done.status_code == 200, done.text
    done = done.json()
    assert done["status"] == ImportStatus.FAILED, done
    assert done["errorCode"] == "failed" and done["error"]
    assert done["formId"] is None and await _gone(body["formId"])
    assert await container.form_import_repo().count_active(workspace.id) == 0
