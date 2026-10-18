"""Images respondents load from us (services/image_service.py):

- ``GET /images/unsplash/{photo}``: an Unsplash photo fetched once from the
  fixed host, re-encoded by the sandbox, kept in our bucket and redirected
  to; never an open proxy;
- ``POST /workspaces/{id}/images/import``: an image address copied into our
  bucket, with the SSRF rules of services/image_fetch.py.

No network: the fetch, the sandbox and the bucket are faked."""

import base64
import io
from typing import Any, Coroutine
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from PIL import Image

from backend.app.container import container
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services import image_fetch, image_service
from backend.app.services.image_fetch import FetchedImage, FetchRefused
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.sandbox import SandboxUnavailable
from backend.config import settings

API = "/api/v1"
STORAGE = "https://cdn.example.org"
BUCKET = "forms-bucket"
PUBLIC_API = "https://forms.example.org/api/v1"


def jpeg(size=(64, 40), colour=(10, 20, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="JPEG")
    return buffer.getvalue()


FETCHED = jpeg()
REENCODED = jpeg(colour=(1, 2, 3))


class FakeFetch:
    def __init__(self):
        self.calls = []
        self.raises = None
        self.result = FetchedImage(FETCHED, "image/jpeg")

    async def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.raises:
            raise self.raises
        return self.result


class FakeSandbox:
    def __init__(self):
        self.calls = []
        self.raises = None

    async def __call__(self, data):
        self.calls.append(data)
        if self.raises:
            raise self.raises
        return {
            "format": "jpeg",
            "content_type": "image/jpeg",
            "width": 64,
            "height": 40,
            "data": base64.b64encode(REENCODED).decode("ascii"),
        }


class FakeBucket:
    def __init__(self):
        self.objects = {}

    def exists(self, key):
        return key in self.objects

    def put(self, body, key, content_type):
        assert key.startswith("public/")
        self.objects[key] = (body, content_type)
        return container.aws_service().public_url_of(key)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    # the test client connects from 127.0.0.1: it is the proxy whose
    # X-Forwarded-For is believed (the default trusts nobody)
    monkeypatch.setattr(settings.api_settings, "TRUSTED_PROXIES", "127.0.0.1")
    monkeypatch.setattr(settings.aws_settings, "PUBLIC_URL", STORAGE)
    monkeypatch.setattr(settings.aws_settings, "BUCKET", BUCKET)
    service = container.image_service()
    service._known.clear()
    fetch, sandbox, bucket = FakeFetch(), FakeSandbox(), FakeBucket()
    monkeypatch.setattr(image_service, "fetch_image", fetch)
    monkeypatch.setattr(image_service, "_process_in_sandbox", sandbox)
    aws = container.aws_service()
    monkeypatch.setattr(
        aws, "public_object_exists", MagicMock(side_effect=bucket.exists)
    )
    monkeypatch.setattr(aws, "put_public_object", MagicMock(side_effect=bucket.put))
    yield fetch, sandbox, bucket
    service._known.clear()


@pytest.fixture()
def fetch(setup):
    return setup[0]


@pytest.fixture()
def sandbox(setup):
    return setup[1]


@pytest.fixture()
def bucket(setup):
    return setup[2]


def unsplash(path: str) -> str:
    return f"{API}/images/unsplash/{path}"


# --- Unsplash through our server ---------------------------------------------


async def test_a_photo_is_fetched_once_reencoded_stored_and_redirected_to(
    client: AsyncClient, fetch, sandbox, bucket
):
    response = await client.get(unsplash("photo-1?w=1000&q=75&ixid=abc&cs=tinysrgb"))
    assert response.status_code == 302, response.text
    location = response.headers["location"]
    assert location.startswith(f"{STORAGE}/")
    assert "/public/image-cache/unsplash/" in location
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "max-age" in response.headers["cache-control"]
    # only the fixed host, only allow-listed and rounded parameters
    [(url, kwargs)] = fetch.calls
    assert url == "https://images.unsplash.com/photo-1?fit=max&h=3840&q=80&w=1080"
    assert kwargs == {"allowed_hosts": {"images.unsplash.com"}, "max_redirects": 0}
    # the sandbox's re-encoding is what is stored, never the fetched bytes
    assert sandbox.calls == [FETCHED]
    [(body, content_type)] = bucket.objects.values()
    assert body == REENCODED and content_type == "image/jpeg"


async def test_cached_photos_are_not_fetched_again(client: AsyncClient, fetch, bucket):
    first = await client.get(unsplash("photo-1?w=1000"))
    # rounded to the same width: the same copy
    again = await client.get(unsplash("photo-1?w=1050&ixlib=rb"))
    assert first.headers["location"] == again.headers["location"]
    assert len(fetch.calls) == 1
    # another process (no memory of it) finds it in the bucket
    container.image_service()._known.clear()
    third = await client.get(unsplash("photo-1?w=1080"))
    assert third.headers["location"] == first.headers["location"]
    assert len(fetch.calls) == 1 and len(bucket.objects) == 1
    # another size is another copy
    await client.get(unsplash("photo-1?w=640"))
    assert len(fetch.calls) == 2 and len(bucket.objects) == 2


@pytest.mark.parametrize(
    "path",
    [
        "..%2F..%2Fworkspaces",
        "photo-1%2F..%2F..",
        "a/b/c",
        "-photo",
        "photo%00",
        "https:%2F%2Fevil.test%2Fx.png",
        "evil.test/x.png/y",
        "..",
    ],
)
async def test_only_photo_paths_are_served(client: AsyncClient, fetch, path):
    response = await client.get(unsplash(path))
    assert response.status_code == 404
    assert fetch.calls == []


@pytest.mark.parametrize(
    "query",
    [
        "w=abc",
        "w=10&w=20",
        "q=0",
        "q=101",
        "fm=gif",
        "fit=evil",
        "crop=evil",
        "crop=faces",
        "crop=top,left",
        "w=99999999",
    ],
)
async def test_bad_sizing_parameters_are_refused(client: AsyncClient, fetch, query):
    response = await client.get(unsplash(f"photo-1?{query}"))
    assert response.status_code == 400
    assert fetch.calls == []


async def test_other_parameters_never_reach_unsplash(client: AsyncClient, fetch):
    response = await client.get(
        unsplash("photo-1?url=https://evil.test/x&host=evil.test&fm=avif&auto=format")
    )
    assert response.status_code == 302
    [(url, _)] = fetch.calls
    assert url == "https://images.unsplash.com/photo-1?fit=max&fm=webp&h=3840&w=1920"


@pytest.mark.parametrize(
    "error,status",
    [
        (FetchRefused("too_large", "big"), 502),
        (FetchRefused("not_image", "html"), 502),
        (FetchRefused("too_many_redirects", "moved"), 502),
    ],
)
async def test_what_unsplash_answers_is_checked(
    client: AsyncClient, fetch, bucket, error, status
):
    fetch.raises = error
    response = await client.get(unsplash("photo-1"))
    assert response.status_code == status
    assert bucket.objects == {}


async def test_a_file_the_sandbox_refuses_is_not_stored(
    client: AsyncClient, sandbox, bucket
):
    sandbox.raises = DocumentRefused("unreadable", "no")
    assert (await client.get(unsplash("photo-1"))).status_code == 502
    assert bucket.objects == {}


async def test_a_fetched_file_that_is_not_an_image_never_reaches_the_sandbox(
    client: AsyncClient, fetch, sandbox, bucket
):
    fetch.result = FetchedImage(b"<svg onload=alert(1)>", "image/jpeg")
    assert (await client.get(unsplash("photo-1"))).status_code == 502
    assert sandbox.calls == [] and bucket.objects == {}


async def test_without_the_sandbox_nothing_is_decoded_here(
    client: AsyncClient, sandbox, bucket
):
    sandbox.raises = SandboxUnavailable("down")
    assert (await client.get(unsplash("photo-1"))).status_code == 503
    assert bucket.objects == {}


async def test_requests_are_limited_per_client(client: AsyncClient, fetch, monkeypatch):
    monkeypatch.setattr(settings.api_settings, "IMAGE_PROXY_FETCHES_PER_WINDOW", 2)
    for n in range(2):
        assert (await client.get(unsplash(f"photo-{n}"))).status_code == 302
    # a third photo to fetch: refused; a cached one still served
    limited = await client.get(unsplash("photo-9"))
    assert limited.status_code == 429 and "retry-after" in limited.headers
    assert (await client.get(unsplash("photo-0"))).status_code == 302
    monkeypatch.setattr(settings.api_settings, "IMAGE_PROXY_PER_WINDOW", 4)
    assert (await client.get(unsplash("photo-0"))).status_code == 429
    assert len(fetch.calls) == 2


def from_ip(address: str) -> dict:
    # the test client connects from loopback, a trusted proxy: the hop it
    # names is the client
    return {"X-Forwarded-For": address}


async def test_all_clients_together_fetch_a_bounded_number_of_photos(
    client: AsyncClient, fetch, monkeypatch
):
    monkeypatch.setattr(
        settings.api_settings, "IMAGE_PROXY_GLOBAL_FETCHES_PER_WINDOW", 3
    )
    for n in range(3):
        response = await client.get(
            unsplash(f"photo-{n}"), headers=from_ip(f"203.0.113.{n + 1}")
        )
        assert response.status_code == 302
    # a fresh address, well under its own limit, still can't make us fetch
    refused = await client.get(unsplash("photo-9"), headers=from_ip("198.51.100.7"))
    assert refused.status_code == 429 and "retry-after" in refused.headers
    assert len(fetch.calls) == 3
    # cached photos are still served to anyone
    again = await client.get(unsplash("photo-1"), headers=from_ip("198.51.100.7"))
    assert again.status_code == 302


async def test_an_ipv6_client_is_limited_by_its_64(
    client: AsyncClient, fetch, monkeypatch
):
    monkeypatch.setattr(settings.api_settings, "IMAGE_PROXY_FETCHES_PER_WINDOW", 2)
    for n in range(2):
        response = await client.get(
            unsplash(f"photo-{n}"), headers=from_ip(f"2001:db8:1:2::{n + 1}")
        )
        assert response.status_code == 302
    # another address in the same /64: the same budget
    same = await client.get(
        unsplash("photo-8"), headers=from_ip("2001:db8:1:2:ffff::9")
    )
    assert same.status_code == 429
    # another /64: its own
    other = await client.get(unsplash("photo-9"), headers=from_ip("2001:db8:1:3::1"))
    assert other.status_code == 302


def test_rate_limit_keys():
    from backend.app.utils.client_ip import rate_limit_key

    assert rate_limit_key("203.0.113.9") == "203.0.113.9"
    assert rate_limit_key("2001:db8:1:2::1") == rate_limit_key("2001:db8:1:2:ab::7")
    assert rate_limit_key("2001:db8:1:2::1") == "2001:db8:1:2::/64"
    assert rate_limit_key("2001:db8:1:3::1") != rate_limit_key("2001:db8:1:2::1")
    assert rate_limit_key("::ffff:203.0.113.9") == "203.0.113.9"
    assert rate_limit_key(None) == rate_limit_key("garbage") == "unknown"


# --- an image address copied in ------------------------------------------------


def import_url(workspace) -> str:
    return f"{API}/workspaces/{workspace.id}/images/import"


async def test_an_address_is_copied_into_our_storage(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
    fetch,
    sandbox,
    bucket,
):
    response = await client.post(
        import_url(workspace),
        cookies=test_user_cookies,
        json={"url": "https://photos.example.org/cat.jpg"},
    )
    assert response.status_code == 200, response.text
    url = response.json()["url"]
    assert url.startswith(f"{STORAGE}/")
    assert f"/public/media/{workspace.id}/" in url
    assert url.endswith(".jpg")
    assert fetch.calls[0][0] == "https://photos.example.org/cat.jpg"
    assert sandbox.calls == [FETCHED]
    [(body, _)] = bucket.objects.values()
    assert body == REENCODED


@pytest.mark.parametrize(
    "pasted,expected",
    [
        # Unsplash's address is stored by its canonical form (pages load it
        # through our route); its tracking parameters are dropped
        (
            "https://images.unsplash.com/photo-1?ixid=a&w=1080",
            "https://images.unsplash.com/photo-1?w=1080",
        ),
        # an address of our route is stored as the canonical Unsplash one
        (
            f"{PUBLIC_API}/images/unsplash/photo-1?w=1080",
            "https://images.unsplash.com/photo-1?w=1080",
        ),
        (f"{STORAGE}/{BUCKET}/public/x.png", f"{STORAGE}/{BUCKET}/public/x.png"),
    ],
)
async def test_first_party_and_unsplash_addresses_need_no_copy(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
    fetch,
    pasted,
    expected,
):
    response = await client.post(
        import_url(workspace), cookies=test_user_cookies, json={"url": pasted}
    )
    assert response.status_code == 200
    assert response.json()["url"] == expected
    assert fetch.calls == []


@pytest.mark.parametrize(
    "code", ["not_allowed", "too_large", "not_image", "unreachable", "invalid_url"]
)
async def test_a_refused_copy_says_so_plainly(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
    fetch,
    bucket,
    code,
):
    fetch.raises = FetchRefused(code, "internal detail")
    response = await client.post(
        import_url(workspace),
        cookies=test_user_cookies,
        json={"url": "https://photos.example.org/cat.jpg"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == code
    assert body["message"].startswith("We couldn't copy that image.")
    assert body["message"].endswith("Upload it instead.")
    assert "internal detail" not in body["message"]
    assert bucket.objects == {}


async def test_the_real_fetcher_refuses_an_address_inside_our_network(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
    monkeypatch,
    bucket,
):
    monkeypatch.setattr(image_service, "fetch_image", image_fetch.fetch_image)
    lookups = []

    async def resolve(host, port=443):
        lookups.append(host)
        return ["169.254.169.254"]

    def no_connection(*args):
        raise AssertionError("no connection may be made")

    monkeypatch.setattr(image_fetch, "resolve", resolve)
    monkeypatch.setattr(image_fetch, "network_backend", no_connection)
    response = await client.post(
        import_url(workspace),
        cookies=test_user_cookies,
        json={"url": "https://metadata.example.org/latest/meta-data"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "not_allowed"
    assert lookups == ["metadata.example.org"] and bucket.objects == {}


async def test_copying_needs_the_sandbox(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
    sandbox,
    bucket,
):
    sandbox.raises = SandboxUnavailable("down")
    response = await client.post(
        import_url(workspace),
        cookies=test_user_cookies,
        json={"url": "https://photos.example.org/cat.jpg"},
    )
    assert response.status_code == 503
    assert bucket.objects == {}


async def test_copying_needs_form_edit_in_the_workspace(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies_1: dict[str, str],
    fetch,
):
    anonymous = await client.post(
        import_url(workspace), json={"url": "https://photos.example.org/cat.jpg"}
    )
    assert anonymous.status_code == 401
    outsider = await client.post(
        import_url(workspace),
        cookies=test_user_cookies_1,
        json={"url": "https://photos.example.org/cat.jpg"},
    )
    assert outsider.status_code == 403
    assert fetch.calls == []


async def test_copies_are_limited_per_person(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
    fetch,
    monkeypatch,
):
    monkeypatch.setattr(settings.api_settings, "IMAGE_IMPORTS_PER_WINDOW", 1)
    body = {"url": "https://photos.example.org/cat.jpg"}
    first = await client.post(
        import_url(workspace), cookies=test_user_cookies, json=body
    )
    assert first.status_code == 200
    second = await client.post(
        import_url(workspace), cookies=test_user_cookies, json=body
    )
    assert second.status_code == 429
    assert len(fetch.calls) == 1
