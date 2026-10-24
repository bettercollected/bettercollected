"""The checks, in the order they run (docs/smoke-test.md):

7  public endpoints answer (first: nothing else is worth trying without them)
3  the standing responses export and decrypt (created on the first run)
1  a respondent signs in with an emailed code (this run's plus-address)
2  a form is created, published, answered in the browser and read back
5  that form is served on the test custom domain
4  a deletion request: filed in the portal, declined by staff (the API key),
   and the respondent sees "Not deleted", never "Deleted"
6  Google Forms: the import mode, the imported test form, the import itself

Afterwards everything this run created is deleted again: its form (with its
response), its respondent account and its code mail. The standing set stays.
Staff actions use the scoped API key only; the browser is a respondent.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlsplit

from smoke import forms
from smoke.browser import FlowError, Session
from smoke.config import OBJECT_ID, Config
from smoke.http import Http, HttpError
from smoke.mailbox import Mailbox
from smoke.report import Abort, Report

DECLINE_REASON = "legal_obligation"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass
class State:
    api_base: str = ""
    forms_base: str = ""
    workspace_id: str = ""
    handle: str = ""
    standing_form: str = ""
    standing_created: bool = False
    run_form: str = ""
    run_slug: str = ""
    run_response: str = ""
    signed_in: bool = False
    notes: List[str] = field(default_factory=list)


def is_local(url: str) -> bool:
    return (urlsplit(url).hostname or "") in LOCAL_HOSTS


def public_config(script: Any) -> Dict[str, str]:
    """The web app's /api/config script (``window.PUBLIC_CONFIG = {...}``)."""
    text = script if isinstance(script, str) else ""
    match = re.search(r"window\.PUBLIC_CONFIG\s*=\s*(\{.*\})", text, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str)}


def same_site(a: str, b: str) -> bool:
    """Both on one site: the same host, both local, or the same last two
    labels (admin.example.com and example.com)."""
    host_a, host_b = urlsplit(a).hostname or "", urlsplit(b).hostname or ""
    if host_a == host_b or (host_a in LOCAL_HOSTS and host_b in LOCAL_HOSTS):
        return True
    site_a, site_b = host_a.split(".")[-2:], host_b.split(".")[-2:]
    return len(site_a) == 2 and site_a == site_b


def script_paths(html: str) -> List[str]:
    """The web app's own script chunks named in a page (same origin only)."""
    paths = re.findall(r'(?:src|href)="(/_next/static/[A-Za-z0-9/_.~-]+\.js)"', html)
    return list(dict.fromkeys(paths))


def api_urls(script: str) -> List[str]:
    """Absolute ``.../api/v1`` addresses in a script."""
    return re.findall(
        r"[\"'](https?://[A-Za-z0-9.-]+(?::\d{1,5})?/api/v1)[\"'/]", script
    )


def forms_base_from(config_values: Dict[str, str], app_url: str) -> str:
    domain = config_values.get("FORM_DOMAIN", "").strip().strip("/")
    scheme = config_values.get("HTTP_SCHEME", "").strip() or "https://"
    if not domain or not re.fullmatch(r"[A-Za-z0-9.-]+(:\d{1,5})?", domain):
        return app_url
    if scheme not in ("http://", "https://"):
        scheme = "https://"
    return f"{scheme}{domain}"


class Suite:
    def __init__(
        self,
        config: Config,
        report: Report,
        mailbox: Mailbox,
        playwright,
        debug_dir: Optional[Path] = None,
    ) -> None:
        self.config = config
        self.report = report
        self.mailbox = mailbox
        self.playwright = playwright
        self.debug_dir = debug_dir
        self.redactor = report.redactor
        self.state = State()
        self.respondent: Optional[Session] = None
        self.app = Http(config.app_url, headers={"Accept": "*/*"})
        self.api: Optional[Http] = None
        self.key: Optional[Http] = None

    # -- helpers -----------------------------------------------------------------
    def session(self) -> Session:
        return Session(self.playwright, self.redactor, self.debug_dir)

    def _connect_api(self, api_base: str) -> None:
        parts = urlsplit(api_base)
        if parts.scheme != "https" and not is_local(api_base):
            raise Abort("refusing to send the API key over plain http")
        if not self.config.api_url and not same_site(self.config.app_url, api_base):
            raise Abort(
                "the API found is on another site than the app (pass --api-url)"
            )
        self.state.api_base = api_base
        self.api = Http(api_base)
        self.key = Http(
            api_base + "/public/v1",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
        )

    def _api_base(self) -> str:
        if self.config.api_url:
            return self.config.api_url
        # <app>/api/v1 first, then what the app's scripts name, most named first
        for candidate in [self.config.app_url + "/api/v1"] + self._api_from_bundle():
            if self._answers(candidate):
                return candidate
        return self._discover_api()

    @staticmethod
    def _answers(candidate: str) -> bool:
        try:
            return isinstance(Http(candidate).get("/providers").body, list)
        except (HttpError, OSError, ValueError):
            return False

    def _api_from_bundle(self) -> List[str]:
        """The API addresses built into the web app's scripts."""
        try:
            page = self.app.get("/login").body
        except (HttpError, OSError):
            return []
        found: Dict[str, int] = {}
        for path in script_paths(page if isinstance(page, str) else "")[:80]:
            try:
                text = self.app.get(path).body
            except (HttpError, OSError):
                continue
            for url in api_urls(text if isinstance(text, str) else ""):
                found[url] = found.get(url, 0) + 1
        return sorted(found, key=lambda u: -found[u])[:5]

    def _discover_api(self) -> str:
        """The API the web app calls, seen from its own requests (the
        workspace's portal page looks the workspace up first thing)."""
        session = self.session()
        try:
            with session.page.expect_request(
                lambda r: "/api/v1/" in r.url, timeout=30_000
            ) as seen:
                session.page.goto(
                    f"{self.state.forms_base or self.config.app_url}/"
                    f"{quote(self.config.workspace)}"
                )
            url = seen.value.url
        except Exception:
            raise Abort("could not find the API address (pass --api-url)")
        finally:
            session.close()
        prefix = url.split("/api/v1/", 1)[0] + "/api/v1"
        if not prefix.startswith(("http://", "https://")):
            raise Abort("could not find the API address (pass --api-url)")
        return prefix

    def _resolve_workspace(self) -> None:
        assert self.api is not None
        wanted = self.config.workspace
        body = None
        if OBJECT_ID.match(wanted):
            try:
                body = self.api.get(f"/workspaces/{wanted}").body
            except HttpError as error:
                if error.status not in (404, 422):
                    raise
        if not isinstance(body, dict) or not body.get("id"):
            body = self.api.get(f"/workspaces?workspace_name={quote(wanted)}").body
        if not isinstance(body, dict) or not body.get("id"):
            raise Abort("SMOKE_WORKSPACE_ID names no workspace")
        self.state.workspace_id = str(body["id"])
        self.state.handle = str(
            body.get("workspaceName") or body.get("workspace_name") or ""
        )
        if not self.state.handle:
            raise Abort("the workspace has no name to build its form links")

    def _in_workspace(self, form_id: str) -> bool:
        """Whether a published form of the key's workspace is one of the
        configured workspace's (the key's workspace must be the test one)."""
        assert self.api is not None
        try:
            self.api.get(
                f"/workspaces/{self.state.workspace_id}/forms/{quote(form_id)}?published=true"
            )
            return True
        except HttpError as error:
            if error.status in (403, 404):
                return False
            raise

    def form_url(self, slug: str) -> str:
        return f"{self.state.forms_base}/{quote(self.state.handle)}/forms/{quote(slug)}"

    def _all_forms(self) -> List[dict]:
        assert self.key is not None
        items: List[dict] = []
        for page in range(1, 11):
            body = self.key.get(f"/forms?page={page}&size=100").body or {}
            batch = body.get("items", []) if isinstance(body, dict) else []
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def _responses(self, form_id: str) -> List[dict]:
        assert self.key is not None
        body = self.key.get(f"/forms/{quote(form_id)}/responses?page=1&size=100").body
        items = body.get("items", []) if isinstance(body, dict) else []
        details = []
        for item in items:
            response_id = str(item.get("responseId", ""))
            detail = self.key.get(
                f"/forms/{quote(form_id)}/responses/{quote(response_id)}"
            ).body
            if isinstance(detail, dict):
                details.append(detail)
        return details

    def _publish(self, form_id: str) -> str:
        assert self.key is not None
        body = self.key.post(f"/forms/{quote(form_id)}/publish").body or {}
        slug = body.get("slug") if isinstance(body, dict) else None
        if not slug:
            raise FlowError("publishing gave no share slug")
        return str(slug)

    # -- the run ----------------------------------------------------------------------
    def run(self) -> None:
        try:
            self.check_public_endpoints()
            self.check_standing_set()
            self.check_sign_in()
            self.check_form_round_trip()
            self.check_custom_domain()
            self.check_deletion_request()
            self.check_google_import()
        except Abort:
            pass  # the check that stopped the run says why
        finally:
            self.cleanup()

    def check_public_endpoints(self) -> None:
        with self.report.check("7", "Public endpoints answer") as c:
            reply = self.app.get("/", expect=(200,))
            c.note(f"app {reply.status}")
            script = self.app.get("/api/config", expect=(200,))
            values = public_config(script.body)
            if not values:
                c.fail("the app's /api/config holds no public config")
            self.state.forms_base = forms_base_from(values, self.config.app_url)
            self._connect_api(self._api_base())
            assert self.api is not None
            providers = self.api.get("/providers").body
            c.note(
                f"providers {len(providers) if isinstance(providers, list) else '?'}"
            )
            openapi = self.api.get("/public/v1/openapi.json").body
            if not (isinstance(openapi, dict) and openapi.get("openapi")):
                c.fail("the public API document is missing")
            self._resolve_workspace()
            c.id("workspace", self.state.workspace_id)
            c.note("API, workspace lookup and public API document answer")
        if self.report.checks[-1].status == "fail" or self.api is None:
            raise Abort("the public endpoints do not answer")

    def check_standing_set(self) -> None:
        assert self.key is not None
        with self.report.check("3", "Standing responses export and decrypt") as c:
            matches = [
                f for f in self._all_forms() if f.get("title") == forms.STANDING_TITLE
            ]
            if len(matches) > 1:
                c.fail("more than one standing form: keep one")
                return
            if matches:
                form_id = str(matches[0]["formId"])
                # published on creation; publish again if someone unpublished it
                slug = str(matches[0].get("slug") or "") or self._publish(form_id)
            else:
                form_id = str(
                    self.key.post("/forms", forms.standing_spec(), expect=(201,)).body[
                        "formId"
                    ]
                )
                self.state.standing_created = True
                slug = self._publish(form_id)
            self.state.standing_form = form_id
            c.id("form", form_id)
            if not self._in_workspace(slug):
                raise Abort(
                    "the API key's workspace is not SMOKE_WORKSPACE_ID: stopping"
                )
            stored = self._responses(form_id)
            if not stored:
                self._answer_standing(slug)
                stored = self._responses(form_id)
                c.note(f"standing set created this run ({len(stored)} responses)")
            problems = forms.compare_standing(stored)
            for problem in problems:
                c.fail(problem)
            if not problems:
                c.note(f"{len(stored)} responses read back and decrypted as stored")
            # a set made this run is complete now: keep it
            self.state.standing_created = False

    def _answer_standing(self, slug: str) -> None:
        session = self.session()
        try:
            for answers in forms.STANDING_RESPONSES:
                session.open_form(self.form_url(slug), forms.STANDING_TITLE)
                session.fill(answers)
                session.submit(self.state.standing_form)
        finally:
            session.close()

    def check_sign_in(self) -> None:
        assert self.api is not None
        with self.report.check("1", "Sign-in with an emailed code") as c:
            self.respondent = self.session()
            address = self.config.run_address
            self.respondent.sign_in(
                self.state.forms_base,
                self.state.workspace_id,
                f"/{self.state.handle}",
                address,
                lambda since: self.mailbox.wait_for_code(address, since),
            )
            status, _ = self.respondent.api("GET", f"{self.state.api_base}/auth/status")
            if status != 200:
                c.fail(f"the session is not signed in ({status})")
                return
            self.state.signed_in = True
            c.note(f"code read from the mailbox ({self.config.mailbox.kind})")

    def check_form_round_trip(self) -> None:
        assert self.key is not None
        with self.report.check("2", "Create, publish, submit, read back") as c:
            title = forms.run_title(self.config.run_tag)
            created = self.key.post(
                "/forms", forms.run_spec(self.config.run_tag), expect=(201,)
            )
            self.state.run_form = str(created.body["formId"])
            c.id("form", self.state.run_form)
            self.state.run_slug = self._publish(self.state.run_form)
            session = self.respondent if self.state.signed_in else self.session()
            try:
                session.open_form(self.form_url(self.state.run_slug), title)
                session.fill({forms.RUN_FIELD: self.config.run_tag})
                if session is self.respondent:
                    # identified, so the respondent's portal lists the
                    # response and its deletion request (check 4)
                    session.share_identity()
                session.submit(self.state.run_form)
            finally:
                if session is not self.respondent:
                    session.close()
            stored = self._responses(self.state.run_form)
            if len(stored) != 1:
                c.fail(f"expected 1 response, found {len(stored)}")
                return
            self.state.run_response = str(stored[0].get("responseId", ""))
            c.id("response", self.state.run_response)
            values = forms.answers_by_field(stored[0].get("answers"))
            if values.get(forms.RUN_FIELD) != self.config.run_tag:
                c.fail("the response read back differs from the answer given")
            else:
                c.note("answer read back as given")

    def check_custom_domain(self) -> None:
        with self.report.check("5", "Form on the custom domain") as c:
            if not self.state.run_slug:
                c.skip("no run form (check 2 failed)")
                return
            scheme = "http" if is_local(self.config.app_url) else "https"
            url = f"{scheme}://{self.config.custom_domain}/forms/{quote(self.state.run_slug)}"
            session = self.session()
            try:
                status = session.page_shows(url, forms.run_title(self.config.run_tag))
            finally:
                session.close()
            if status != 200:
                c.fail(f"the custom domain answered {status}")
            else:
                c.note("the run form renders on the custom domain")

    def check_deletion_request(self) -> None:
        assert self.key is not None
        with self.report.check("4", "Deletion request: filed, declined, status") as c:
            if not (self.state.signed_in and self.state.run_response):
                c.skip("needs the signed-in respondent's response (checks 1 and 2)")
                return
            assert self.respondent is not None
            form_id, response_id = self.state.run_form, self.state.run_response
            self.respondent.request_deletion(
                self.state.forms_base, self.state.handle, response_id
            )
            base = f"/forms/{quote(form_id)}/responses/{quote(response_id)}"
            detail = self.key.get(base).body or {}
            if (detail.get("deletionRequest") or {}).get("status") != "pending":
                c.fail("staff do not see the request as pending")
                return
            closed = (
                self.key.post(
                    base + "/deletion-request/close",
                    {"outcome": "declined", "reason": DECLINE_REASON},
                ).body
                or {}
            )
            if closed.get("status") != "declined":
                c.fail("closing the request as declined did not stick")
                return
            text = self.respondent.deletion_status_text(
                self.state.forms_base,
                self.state.handle,
                forms.run_title(self.config.run_tag),
            )
            if text.startswith("Deleted"):
                c.fail("the respondent sees a declined request as deleted")
            elif not text.startswith("Not deleted:"):
                c.fail("the respondent does not see the request as declined")
            status, body = self.respondent.api(
                "GET",
                f"{self.state.api_base}/workspaces/{self.state.workspace_id}"
                "/submissions?request_for_deletion=true",
            )
            items = body.get("items", []) if isinstance(body, dict) else []
            mine = [i for i in items if str(i.get("responseId")) == response_id]
            if status != 200 or not mine or mine[0].get("status") != "declined":
                c.fail("the portal's data does not say declined")
            if not c.failed:
                c.note("respondent sees 'Not deleted' with the reason")

    def check_google_import(self) -> None:
        assert self.api is not None and self.key is not None
        with self.report.check("6", "Google Forms import") as c:
            providers = self.api.get("/providers").body or []
            google = next(
                (
                    p
                    for p in providers
                    if isinstance(p, dict)
                    and str(p.get("providerName", p.get("provider_name"))) == "google"
                ),
                None,
            )
            if google is None:
                c.skip("Google Forms is not offered on this instance")
                return
            mode = str(google.get("importMode") or google.get("import_mode") or "on")
            c.note(f"import mode {mode}")
            form_id = self.config.google_form_id
            c.id("google form", form_id)
            readable = self._imported_form_readable(c, form_id)
            if mode == "readonly":
                if not readable:
                    c.fail("the imported test form is not readable")
                if self.state.signed_in and self.respondent is not None:
                    status, body = self.respondent.api(
                        "GET", f"{self.state.api_base}/google/forms"
                    )
                    code = body.get("code") if isinstance(body, dict) else None
                    if status == 403 and code == "google_forms_readonly":
                        c.note("a new import is refused with the read-only message")
                    else:
                        c.fail(f"a new import is not refused as read-only ({status})")
                else:
                    c.skip("the refusal needs a signed-in session (check 1)")
                return
            # mode "on": the import runs as the account that holds the stored
            # Google connection; the suite has no session of that account.
            c.skip(
                "the import itself needs a session of the account holding the "
                "Google connection (owner decision, see docs/smoke-test.md)"
            )

    def _imported_form_readable(self, c, form_id: str) -> bool:
        assert self.key is not None
        try:
            stored = self._responses(form_id)
        except HttpError as error:
            if error.status == 404:
                c.note("the test Google Form is not imported in the workspace")
                return False
            raise
        unreadable = [r for r in stored if not forms.answers_by_field(r.get("answers"))]
        if unreadable:
            c.fail(f"{len(unreadable)} imported response(s) do not read")
            return False
        c.note(f"imported form readable ({len(stored)} responses)")
        return True

    # -- cleanup ---------------------------------------------------------------------
    def cleanup(self) -> None:
        report = self.report
        for form_id, what in (
            (self.state.run_form, "run form"),
            (
                self.state.standing_form if self.state.standing_created else "",
                "unfinished standing form",
            ),
        ):
            if not form_id or self.key is None:
                continue
            try:
                self.key.delete(f"/forms/{quote(form_id)}", expect=(204,))
                report.note_cleanup(f"{what} {form_id} deleted")
            except Exception as error:
                report.note_cleanup(f"{what} {form_id} NOT deleted ({error})")
        if self.respondent is not None:
            if self.state.signed_in:
                try:
                    status, _ = self.respondent.api(
                        "POST",
                        f"{self.state.api_base}/auth/user/delete/workflow",
                        {"reasonForDeletion": "Automated smoke test account"},
                    )
                    report.note_cleanup(f"run account deletion requested ({status})")
                except Exception as error:
                    report.note_cleanup(
                        f"run account NOT deleted ({type(error).__name__})"
                    )
            try:
                self.respondent.close()
            except Exception:
                pass
        try:
            report.note_cleanup(self.mailbox.cleanup(self.config.run_address))
        except Exception as error:
            report.note_cleanup(f"mailbox cleanup failed ({type(error).__name__})")
