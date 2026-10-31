"""A small JSON HTTP client (standard library only).

No retry storms: a 429 is waited out once when its Retry-After is short, and
nothing else is retried. Error messages carry the status and the API's error
code, never a request or response body that could hold a value.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional

USER_AGENT = "bettercollected-smoke/1"
MAX_RETRY_AFTER = 30


class HttpError(Exception):
    def __init__(
        self,
        method: str,
        path: str,
        status: int,
        code: str = "",
        problems: tuple = (),
    ) -> None:
        self.status = status
        self.code = code
        # the codes of the 422's ``problems`` (e.g. why a form can't be
        # published): codes only, never their messages
        self.problems = tuple(problems)
        detail = f" ({code})" if code else ""
        if self.problems:
            detail = f" ({code}: {', '.join(self.problems)})"
        super().__init__(f"{method} {path} answered {status}{detail}")


@dataclass
class Reply:
    status: int
    headers: dict
    body: Any


def _is_code(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) < 60
        and value.replace("_", "").isalnum()
    )


def _problem_codes(raw: bytes) -> tuple:
    """The ``code`` of each entry of the error body's ``problems`` list (at
    most 10, in order, no repeats); anything that is not a plain code is
    dropped."""
    try:
        body = json.loads(raw)
    except ValueError:
        return ()
    problems = body.get("problems") if isinstance(body, dict) else None
    if not isinstance(problems, list):
        return ()
    codes: list = []
    for problem in problems:
        code = problem.get("code") if isinstance(problem, dict) else None
        if _is_code(code) and code not in codes:
            codes.append(code)
    return tuple(codes[:10])


def _error_code(raw: bytes) -> str:
    try:
        body = json.loads(raw)
    except ValueError:
        return ""
    code = body.get("code") if isinstance(body, dict) else None
    if isinstance(code, str) and code.replace("_", "").isalnum() and len(code) < 60:
        return code
    return ""


class Http:
    def __init__(
        self,
        base_url: str,
        headers: Optional[dict] = None,
        timeout: float = 60,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        self.headers.update(headers or {})
        self.timeout = timeout
        self.sleep = sleep

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        expect: tuple[int, ...] = (200,),
        headers: Optional[dict] = None,
    ) -> Reply:
        data = None
        all_headers = dict(self.headers, **(headers or {}))
        if body is not None:
            data = json.dumps(body).encode()
            all_headers["Content-Type"] = "application/json"
        shown_path = path.split("?", 1)[0]
        for attempt in (1, 2):
            request = urllib.request.Request(
                self.base_url + path, data=data, headers=all_headers, method=method
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                    status = response.status
                    reply_headers = dict(response.headers.items())
            except urllib.error.HTTPError as error:
                raw = error.read() or b""
                status = error.code
                reply_headers = dict(error.headers.items()) if error.headers else {}
                if status == 429 and attempt == 1:
                    retry_after = reply_headers.get("Retry-After", "")
                    if retry_after.isdigit() and int(retry_after) <= MAX_RETRY_AFTER:
                        self.sleep(int(retry_after) + 1)
                        continue
            if status not in expect:
                raise HttpError(
                    method,
                    shown_path,
                    status,
                    _error_code(raw),
                    _problem_codes(raw),
                )
            parsed: Any = None
            if raw:
                try:
                    parsed = json.loads(raw)
                except ValueError:
                    parsed = raw.decode(errors="replace")
            return Reply(status, reply_headers, parsed)
        raise HttpError(method, shown_path, 429, "rate_limited")

    def get(self, path: str, **kwargs) -> Reply:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, body: Any = None, **kwargs) -> Reply:
        return self.request("POST", path, body=body, **kwargs)

    def delete(self, path: str, **kwargs) -> Reply:
        return self.request("DELETE", path, **kwargs)
