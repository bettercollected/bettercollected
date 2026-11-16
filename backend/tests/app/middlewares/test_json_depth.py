"""A request body nested too deeply for the JSON parser is refused cleanly.

``json.loads`` of Python 3.11 fails with a ``RecursionError`` a little under a
thousand levels (a body of ~2 KB of brackets): every route that parsed such a
body (the idempotency fingerprint reads it first) answered 500. The middleware
(middlewares/json_depth.py) refuses a body nested beyond MAX_JSON_DEPTH with
422 ``body_too_deep`` before anything parses it; the places that parse a body
themselves turn a RecursionError into the same answer.

The depths below are the ones measured on the deployed interpreter (983 and 984
failed), the limit and one more, and far beyond.
"""

import json

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.middlewares.json_depth import (
    MAX_BUFFERED_BYTES,
    JsonDepthMiddleware,
)
from backend.app.utils.json_depth import MAX_JSON_DEPTH
from tests.app.controllers.test_editor_ops_save import (  # noqa: F401
    _auth_service_users,
    _etag,
    _ops_url,
    enabled,
    v2_form,
)
from tests.app.controllers.test_mcp_server import (
    MCP_HEADERS,
    MCP_URL,
    _make_key as _make_mcp_key,
)
from tests.app.controllers.test_public_api import (
    BASE,
    SPEC,
    _auth,
    _create,
    _form_count,
    _is_error,
    _token,
)
from tests.app.sso_helpers import sso_on  # noqa: F401
from tests.app.controllers.test_scim import (  # noqa: F401
    OWNER,
    directory,
    members_list,
    scim_on,
    signed,
)

LIMIT = MAX_JSON_DEPTH
TOO_DEEP = [LIMIT + 1, 983, 984, 5000]


def arrays(n: int) -> bytes:
    return b"[" * n + b"]" * n


def objects(n: int) -> bytes:
    return b'{"a":' * n + b"1" + b"}" * n


def mixed(n: int) -> bytes:
    opening = [b'{"a":' if i % 2 else b"[" for i in range(n)]
    closing = [b"}" if i % 2 else b"]" for i in reversed(range(n))]
    return b"".join(opening) + b"1" + b"".join(closing)


SHAPES = [arrays, objects, mixed]
JSON = {"Content-Type": "application/json"}


def refused(response, *, error_key=False):
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "body_too_deep", body
    assert "nested too deeply" in body["message"]
    assert set(body) == ({"code", "message", "error"} if error_key else {"code", "message"})
    return body


# -- the ASGI middleware itself ------------------------------------------------------


class Harness:
    """Drives the middleware over a stand-in app that reads the whole body."""

    def __init__(self):
        self.seen = None
        self.messages = []

    async def app(self, scope, receive, send):
        body = b""
        while True:
            message = await receive()
            self.messages.append(message["type"])
            if message["type"] != "http.request":
                break
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        self.seen = body
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def call(self, chunks, *, method="POST", content_type=b"application/json",
                   length="declared", path="/api/v1/x", extra=(), disconnect=False):
        queue = [
            {"type": "http.request", "body": c, "more_body": i < len(chunks) - 1}
            for i, c in enumerate(chunks)
        ]
        if disconnect:
            queue[-1]["more_body"] = True
            queue.append({"type": "http.disconnect"})
        headers = list(extra)
        if content_type is not None:
            headers.append((b"content-type", content_type))
        if length == "declared":
            headers.append((b"content-length", str(sum(map(len, chunks))).encode()))
        elif length == "chunked":
            headers.append((b"transfer-encoding", b"chunked"))
        elif length:
            headers.append((b"content-length", str(length).encode()))
        scope = {"type": "http", "method": method, "path": path, "headers": headers}
        sent = []

        async def receive():
            if queue:
                return queue.pop(0)
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        await JsonDepthMiddleware(self.app)(scope, receive, send)
        status = next(m["status"] for m in sent if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        return status, body


async def test_a_deep_body_is_refused_and_never_reaches_the_app():
    harness = Harness()
    status, body = await harness.call([arrays(LIMIT + 1)])
    assert status == 422 and json.loads(body)["code"] == "body_too_deep"
    assert harness.seen is None


async def test_a_body_at_the_limit_reaches_the_app_unchanged():
    harness = Harness()
    document = arrays(LIMIT)
    assert await harness.call([document]) == (200, b"ok")
    assert harness.seen == document


async def test_a_body_in_several_chunks_is_checked_as_a_whole():
    harness = Harness()
    document = arrays(LIMIT + 1)
    # no chunk is deep on its own
    chunks = [document[i : i + 50] for i in range(0, len(document), 50)]
    status, _ = await harness.call(chunks, length="chunked")
    assert status == 422 and harness.seen is None
    harness = Harness()
    document = arrays(LIMIT)
    chunks = [document[i : i + 7] for i in range(0, len(document), 7)]
    assert (await harness.call(chunks, length="chunked"))[0] == 200
    assert harness.seen == document


async def test_a_disconnect_in_the_middle_of_the_body_reaches_the_app():
    harness = Harness()
    status, _ = await harness.call([b"[1,", b"2"], disconnect=True)
    assert status == 200
    assert harness.seen == b"[1,2" and harness.messages[-1] == "http.disconnect"


@pytest.mark.parametrize(
    "content_type",
    [b"application/json", b"application/json; charset=utf-8", b"Application/JSON",
     b"application/scim+json", b"application/vnd.api+json", b"text/plain", None],
)
async def test_json_like_bodies_are_checked(content_type):
    harness = Harness()
    status, _ = await harness.call([arrays(LIMIT + 1)], content_type=content_type)
    assert status == 422 and harness.seen is None


@pytest.mark.parametrize(
    "content_type",
    [b"multipart/form-data; boundary=x", b"application/x-www-form-urlencoded",
     b"application/octet-stream", b"image/png", b"text/csv"],
)
async def test_form_posts_and_uploads_are_not_buffered_here(content_type):
    harness = Harness()
    document = arrays(5000)
    assert (await harness.call([document], content_type=content_type))[0] == 200
    assert harness.seen == document


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
async def test_requests_without_a_body_pass_straight_through(method):
    harness = Harness()
    assert (await harness.call([b""], method=method))[0] == 200


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_every_method_that_carries_a_body_is_checked(method):
    harness = Harness()
    assert (await harness.call([arrays(LIMIT + 1)], method=method))[0] == 422


async def test_an_empty_body_passes():
    harness = Harness()
    assert (await harness.call([b""]))[0] == 200 and harness.seen == b""


PAD = b" " * (2 * MAX_BUFFERED_BYTES)


async def test_a_body_that_declares_more_than_the_cap_is_scanned_as_it_is_read():
    """Past the reading cap the pieces go straight on, each scanned: a shallow
    one reaches the app unchanged, a deep one (before or after the padding) is
    refused in place of whatever the app answers."""
    harness = Harness()
    shallow = arrays(LIMIT)
    status, _ = await harness.call([shallow], length=MAX_BUFFERED_BYTES + 1)
    assert status == 200 and harness.seen == shallow
    for chunks in (
        [arrays(LIMIT + 1)],  # deep, then nothing
        [arrays(LIMIT + 1), PAD],  # deep prefix, then padding
        [PAD, arrays(LIMIT + 1)],  # padding, then deep
        [PAD, PAD, arrays(LIMIT + 1)],
    ):
        harness = Harness()
        status, body = await harness.call(chunks, length=MAX_BUFFERED_BYTES + 1)
        assert status == 422 and json.loads(body)["code"] == "body_too_deep"


async def test_a_route_that_answers_before_reading_keeps_its_answer():
    """A route's own 413 on a declared size comes before any body is read:
    nothing was scanned, nothing replaces it."""

    async def refuses(scope, receive, send):
        await send({"type": "http.response.start", "status": 413, "headers": []})
        await send({"type": "http.response.body", "body": b"too large"})

    sent = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "method": "POST", "path": "/x",
        "headers": [(b"content-type", b"application/json"),
                    (b"content-length", str(len(PAD)).encode())],
    }

    async def receive():
        raise AssertionError("the body was read")

    await JsonDepthMiddleware(refuses)(scope, receive, send)
    assert [m.get("status") for m in sent if m["type"] == "http.response.start"] == [413]


async def test_a_chunked_body_past_the_cap_is_scanned_all_the_way():
    piece = b"[1]," * (MAX_BUFFERED_BYTES // 8)
    shallow = [b"[" + piece, piece, piece, b"0]"]
    harness = Harness()
    status, _ = await harness.call(shallow, length="chunked")
    assert status == 200 and harness.seen == b"".join(shallow)
    # a deep start is refused without reading on
    harness = Harness()
    status, _ = await harness.call([arrays(LIMIT + 1) + b" " * 10, piece, piece, piece], length="chunked")
    assert status == 422 and harness.seen is None
    # a deep end, after more than the cap of padding, in the pieces the app reads on its own
    for tail in (arrays(LIMIT + 1), b'"' + b"x" * 100 + b'"' + arrays(LIMIT + 1)):
        harness = Harness()
        status, body = await harness.call([PAD, PAD, tail], length="chunked")
        assert status == 422 and json.loads(body)["code"] == "body_too_deep"
        assert harness.messages[-1] == "http.disconnect"


async def test_a_deep_body_split_across_the_cap_and_a_string_is_still_found():
    harness = Harness()
    # the cap falls inside a string that holds brackets, the nesting follows it
    chunks = [b'["' + b"[" * (MAX_BUFFERED_BYTES + 10) + b"\\", b'"', b'"' + b"[" * (LIMIT + 1)]
    status, _ = await harness.call(chunks, length="chunked")
    assert status == 422


async def test_the_mcp_endpoint_gets_its_own_error_key():
    harness = Harness()
    status, body = await harness.call([arrays(LIMIT + 1)], path="/api/v1/mcp")
    assert status == 422
    assert set(json.loads(body)) == {"code", "message", "error"}
    status, body = await harness.call([arrays(LIMIT + 1)], path="/api/v1/mcp-things")
    assert set(json.loads(body)) == {"code", "message"}


async def test_a_message_that_is_not_http_goes_straight_through():
    seen = []

    async def app(scope, receive, send):
        seen.append(scope["type"])

    await JsonDepthMiddleware(app)({"type": "lifespan"}, None, None)
    assert seen == ["lifespan"]


# -- the public API ----------------------------------------------------------------


class TestPublicApi:
    @pytest.mark.parametrize("shape", SHAPES)
    @pytest.mark.parametrize("levels", TOO_DEEP)
    @pytest.mark.parametrize("keyed", [True, False])
    async def test_create_ops_and_publish_refuse_a_deep_body(
        self, client: AsyncClient, workspace, shape, levels, keyed
    ):
        token = await _token(workspace.id)
        form_id = (await _create(client, token)).json()["formId"]
        before = await _form_count(workspace.id)
        headers = {**JSON, **({"Idempotency-Key": f"k-{levels}-{shape.__name__}"} if keyed else {})}
        for path in ("/forms", f"/forms/{form_id}/ops", f"/forms/{form_id}/publish"):
            response = await client.post(
                BASE + path, content=shape(levels), headers=_auth(token, **headers)
            )
            _is_error(response, 422, "body_too_deep")
        assert await _form_count(workspace.id) == before

    async def test_a_put_and_a_body_sent_as_a_form_are_refused_too(
        self, client: AsyncClient, workspace
    ):
        """The middleware does not look at a form-encoded body (a route reading
        the raw bytes still gets one): the parse itself gives the same answer."""
        token = await _token(workspace.id)
        for levels in (LIMIT + 1, 983, 5000):
            response = await client.post(
                f"{BASE}/forms",
                content=arrays(levels),
                headers=_auth(
                    token,
                    **{
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Idempotency-Key": f"form-{levels}",
                    },
                ),
            )
            _is_error(response, 422, "body_too_deep")

    async def test_a_body_at_the_limit_is_not_refused_for_its_depth(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        for shape in SHAPES:
            response = await client.post(
                f"{BASE}/forms", content=shape(LIMIT),
                headers=_auth(token, **JSON, **{"Idempotency-Key": f"at-{shape.__name__}"}),
            )
            # a document that is not a form spec: the API's usual refusal
            assert response.status_code in (400, 422), response.text
            assert response.json()["code"] != "body_too_deep"

    async def test_a_real_form_still_creates_with_a_key(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        response = await client.post(
            f"{BASE}/forms", json=SPEC, headers=_auth(token, **{"Idempotency-Key": "fine"})
        )
        assert response.status_code == 201, response.text


# -- a body padded past the reading cap ----------------------------------------------

DEEP = arrays(LIMIT + 1)
PADDING = b" " * (2 * MAX_BUFFERED_BYTES)
LONG_STRING = b'"' + b"x" * (2 * MAX_BUFFERED_BYTES) + b'"'

# (name, the body): the nesting before the padding, after it, behind a long string
PADDED = {
    "deep then padding": DEEP + PADDING,
    "padding then deep": PADDING + DEEP,
    "deep object then a long string": b'{"deep":' + DEEP + b',"pad":' + LONG_STRING + b"}",
    "a long string then the deep object": b'{"pad":' + LONG_STRING + b',"deep":' + DEEP + b"}",
}


async def pieces(body: bytes, size: int = 256 * 1024):
    for start in range(0, len(body), size):
        yield body[start : start + size]


class TestPaddedBodies:
    """A body over 1 MiB used to pass the scan untouched: a few KB of nesting
    plus padding reached the parser."""

    @pytest.mark.parametrize("name", PADDED)
    @pytest.mark.parametrize("chunked", [False, True])
    async def test_the_main_api_refuses_it(
        self, client: AsyncClient, workspace, directory, name, chunked
    ):
        body = PADDED[name]
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/scim/resync",
            content=pieces(body) if chunked else body,
            headers=JSON,
            cookies=OWNER,
        )
        refused(response)

    @pytest.mark.parametrize("name", PADDED)
    async def test_the_public_api_refuses_a_chunked_body_with_the_deep_part_in_the_first_mib(
        self, client: AsyncClient, workspace, name
    ):
        """No Content-Length: the first MiB is read and scanned before the
        route runs."""
        if not PADDED[name].startswith((b"{\"deep", b"[")):
            pytest.skip("the nesting comes after the first MiB: see the next test")
        token = await _token(workspace.id)
        for key in (None, "padded"):
            headers = _auth(token, **JSON, **({"Idempotency-Key": key} if key else {}))
            response = await client.post(
                f"{BASE}/forms", content=pieces(PADDED[name]), headers=headers
            )
            _is_error(response, 422, "body_too_deep")

    @pytest.mark.parametrize("name", PADDED)
    @pytest.mark.parametrize("chunked", [False, True])
    async def test_the_public_api_keeps_its_own_size_limit_whatever_the_nesting(
        self, client: AsyncClient, workspace, name, chunked
    ):
        """Its readers stop at 1 MiB with a 413 before any parse (on the
        declared length, or on the running total of a chunked body), so a
        body over that is a 413, never a 500, whether or not it is deep."""
        token = await _token(workspace.id)
        body = PADDED[name]
        response = await client.post(
            f"{BASE}/forms",
            content=pieces(body) if chunked else body,
            headers=_auth(token, **JSON, **{"Idempotency-Key": f"big-{name}-{chunked}"}),
        )
        if response.status_code == 422:  # (the deep part was in the first MiB)
            _is_error(response, 422, "body_too_deep")
        else:
            _is_error(response, 413, "payload_too_large")

    async def test_a_big_body_that_is_not_deep_is_still_a_413_and_a_small_one_still_works(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        padded = b'{"pad":' + LONG_STRING + b"}"
        response = await client.post(
            f"{BASE}/forms", content=padded, headers=_auth(token, **JSON)
        )
        _is_error(response, 413, "payload_too_large")
        response = await client.post(
            f"{BASE}/forms", json=SPEC, headers=_auth(token, **{"Idempotency-Key": "ok"})
        )
        assert response.status_code == 201, response.text


# -- the builder's operations route ------------------------------------------------


class TestBuilderOps:
    @pytest.mark.parametrize("shape", SHAPES)
    @pytest.mark.parametrize("levels", TOO_DEEP)
    async def test_a_deep_ops_body_is_refused(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies, shape, levels
    ):
        etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
        response = await client.post(
            _ops_url(workspace, v2_form.form_id),
            content=shape(levels),
            headers={**JSON, "If-Match": etag, "Idempotency-Key": f"b-{levels}"},
            cookies=test_user_cookies,
        )
        refused(response)

    async def test_an_ops_body_still_applies(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
        response = await client.post(
            _ops_url(workspace, v2_form.form_id),
            json={"ops": [{"op": "update_form_info", "title": "Renamed"}]},
            headers={"If-Match": etag, "Idempotency-Key": "fine"},
            cookies=test_user_cookies,
        )
        assert response.status_code == 200, response.text


# -- other JSON routes --------------------------------------------------------------


class TestOtherRoutes:
    @pytest.mark.parametrize("levels", TOO_DEEP)
    async def test_a_route_with_a_model_body(
        self, client: AsyncClient, workspace, directory, levels
    ):
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/scim/resync",
            content=objects(levels),
            headers=JSON,
            cookies=OWNER,
        )
        refused(response)

    @pytest.mark.parametrize("levels", TOO_DEEP)
    async def test_the_scim_webhook(self, client: AsyncClient, workspace, directory, scim_on, levels):
        polis, _ = scim_on
        body = arrays(levels)
        headers = signed(body, polis.secret(directory.polis_directory_id))
        response = await client.post(
            f"/api/v1/scim/webhook/{directory.id}", content=body, headers=headers
        )
        refused(response)

    async def test_the_scim_webhook_service_itself_answers_400_for_one(
        self, workspace, directory, scim_on
    ):
        """Called directly (as if the body had got past the middleware): the
        signed body nested past the parser is an invalid body, not a crash."""
        polis, _ = scim_on
        body = arrays(5000)
        reply = await container.scim_webhook_service().receive(
            directory.id, signed(body, polis.secret(directory.polis_directory_id)), body
        )
        assert reply.status == 400 and reply.body["code"] == "invalid_body"

    @pytest.mark.parametrize("levels", TOO_DEEP)
    async def test_mcp(self, client: AsyncClient, workspace, levels):
        token = await _make_mcp_key(workspace.id, ["forms:read"])
        response = await client.post(
            MCP_URL,
            content=b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":'
            + arrays(levels)
            + b"}",
            headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"},
            follow_redirects=True,
        )
        refused(response, error_key=True)

    async def test_the_draft_route_answers_the_same_for_a_deep_body(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        response = await client.put(
            f"/api/v1/workspaces/{workspace.id}/forms/{'f' * 24}/drafts",
            content=arrays(5000),
            headers=JSON,
            cookies=test_user_cookies,
        )
        # (the route does not exist for this form: the body is refused first)
        refused(response)

    @pytest.mark.parametrize("levels", [LIMIT + 1, 983, 5000])
    async def test_a_json_field_of_a_multipart_form(
        self, client: AsyncClient, workspace, published_form, levels
    ):
        """A respondent's submission is a multipart form with the answers as
        JSON in one field: the middleware does not buffer a form, the parse
        of the field gives the answer."""
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{published_form.form_id}/response",
            data={"response": arrays(levels).decode()},
        )
        refused(response)
