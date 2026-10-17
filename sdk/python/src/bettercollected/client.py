"""A small typed client for the BetterCollected public API (docs/api)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Mapping, Sequence, TypeVar

import httpx
from urllib.parse import quote

from bettercollected.models import api
from bettercollected.models.spec import FormSpec

API_PATH = "/api/v1/public/v1"
T = TypeVar("T")


class BetterCollectedError(Exception):
    """Any non-2xx answer, with the API's error body."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        errors: list[api.ErrorItem] | None = None,
        retry_after: int | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.errors = errors or []
        self.retry_after = retry_after

    def __str__(self) -> str:
        located = "".join(f"\n  {e.path or '/'}: {e.message}" for e in self.errors)
        return f"{self.message} ({self.code}){located}"


@dataclass(frozen=True)
class Versioned(Generic[T]):
    """A value with the version it was read or written at; pass ``etag``
    as ``if_match`` to change exactly that version."""

    value: T
    etag: str


@dataclass(frozen=True)
class CreatedForm:
    form_id: str
    form: FormSpec
    etag: str


SpecLike = FormSpec | Mapping[str, Any]


def _q(value: str) -> str:
    return quote(str(value), safe="")


def _document(spec: SpecLike) -> Any:
    if isinstance(spec, FormSpec):
        return spec.model_dump(mode="json", by_alias=True, exclude_none=True)
    return spec


class BetterCollected:
    """``BetterCollected(api_key, base_url)``. Keep the key out of source
    code (the CLI reads it from ``BETTERCOLLECTED_API_KEY``)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        if not api_key:
            raise ValueError("api_key is required")
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + API_PATH,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "BetterCollected":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str | None] | None = None,
    ) -> httpx.Response:
        sent = {k: v for k, v in (headers or {}).items() if v is not None}
        params = {k: v for k, v in (params or {}).items() if v is not None}
        response = self._http.request(
            method, path, json=json, params=params or None, headers=sent
        )
        if response.is_success:
            return response
        try:
            body = api.Error.model_validate(response.json())
        except ValueError:
            body = api.Error(code="http_error", message=f"HTTP {response.status_code}")
        retry = response.headers.get("Retry-After")
        raise BetterCollectedError(
            response.status_code,
            body.code,
            body.message,
            body.errors,
            int(retry) if retry and retry.isdigit() else None,
        )

    # -- forms -------------------------------------------------------------

    def list_forms(self, page: int = 1, size: int = 50) -> api.FormList:
        response = self._request("GET", "/forms", params={"page": page, "size": size})
        return api.FormList.model_validate(response.json())

    def create_form(
        self, spec: SpecLike, *, idempotency_key: str | None = None
    ) -> CreatedForm:
        """Create a draft from a whole document; nothing is created on any
        error."""
        response = self._request(
            "POST",
            "/forms",
            json=_document(spec),
            headers={"Idempotency-Key": idempotency_key},
        )
        body = api.CreatedForm.model_validate(response.json())
        return CreatedForm(
            body.form_id,
            FormSpec.model_validate(body.form),
            response.headers.get("ETag", ""),
        )

    def validate_form(self, document: Any) -> api.ValidationResult:
        """Check a document (it may be invalid) without storing it."""
        if isinstance(document, FormSpec):
            document = _document(document)
        response = self._request("POST", "/forms/validate", json=document)
        return api.ValidationResult.model_validate(response.json())

    def get_form(self, form_id: str) -> Versioned[FormSpec]:
        response = self._request("GET", f"/forms/{_q(form_id)}")
        return Versioned(
            FormSpec.model_validate(response.json()), response.headers.get("ETag", "")
        )

    def get_form_document(self, form_id: str) -> Versioned[dict]:
        """The form as plain JSON, exactly as the API sent it."""
        response = self._request("GET", f"/forms/{_q(form_id)}")
        return Versioned(response.json(), response.headers.get("ETag", ""))

    def replace_form(
        self, form_id: str, spec: SpecLike, *, if_match: str
    ) -> Versioned[FormSpec]:
        """Replace a form, only while it is still the version ``if_match``
        names (412 otherwise)."""
        response = self._request(
            "PUT",
            f"/forms/{_q(form_id)}",
            json=_document(spec),
            headers={"If-Match": if_match},
        )
        return Versioned(
            FormSpec.model_validate(response.json()), response.headers.get("ETag", "")
        )

    def preview_replace(self, form_id: str, spec: SpecLike) -> api.ReplacePreview:
        response = self._request(
            "POST", f"/forms/{_q(form_id)}/replace/dry-run", json=_document(spec)
        )
        return api.ReplacePreview.model_validate(response.json())

    def apply_ops(
        self,
        form_id: str,
        ops: Sequence[Mapping[str, Any]],
        *,
        atomic: bool = True,
        if_match: str | None = None,
        idempotency_key: str | None = None,
    ) -> Versioned[api.OpsResult]:
        response = self._request(
            "POST",
            f"/forms/{_q(form_id)}/ops",
            json={"ops": list(ops), "atomic": atomic},
            headers={"If-Match": if_match, "Idempotency-Key": idempotency_key},
        )
        return Versioned(
            api.OpsResult.model_validate(response.json()),
            response.headers.get("ETag", ""),
        )

    def dry_run_ops(
        self, form_id: str, ops: Sequence[Mapping[str, Any]], *, atomic: bool = True
    ) -> api.DryRunResult:
        response = self._request(
            "POST",
            f"/forms/{_q(form_id)}/ops/dry-run",
            json={"ops": list(ops), "atomic": atomic},
        )
        return api.DryRunResult.model_validate(response.json())

    def publish_form(
        self, form_id: str, *, idempotency_key: str | None = None
    ) -> api.PublishResult:
        response = self._request(
            "POST",
            f"/forms/{_q(form_id)}/publish",
            headers={"Idempotency-Key": idempotency_key},
        )
        return api.PublishResult.model_validate(response.json())

    # -- responses ---------------------------------------------------------

    def list_responses(
        self, form_id: str, page: int = 1, size: int = 20
    ) -> api.ResponseList:
        response = self._request(
            "GET",
            f"/forms/{_q(form_id)}/responses",
            params={"page": page, "size": size},
        )
        return api.ResponseList.model_validate(response.json())

    def get_response(self, form_id: str, response_id: str) -> api.ResponseDetail:
        response = self._request(
            "GET", f"/forms/{_q(form_id)}/responses/{_q(response_id)}"
        )
        return api.ResponseDetail.model_validate(response.json())
