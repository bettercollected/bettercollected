"""The browser flows (Playwright, Chromium, headless): a respondent signing in
with an emailed code, answering a form, asking for a submission's deletion and
reading its status, and a form served on the custom domain.

Locators use roles, field ids and the API calls the pages make, not styling;
the browser runs in English so the few button names are stable. No screenshot,
trace or video is ever recorded (they could show a code or an answer), except
into ``debug_dir`` on a local dry run, through the redactor.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Callable, Mapping, Optional
from urllib.parse import quote

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, Response
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from smoke.redact import Redactor

NAV_TIMEOUT_MS = 45_000
STEP_TIMEOUT_MS = 20_000
SUBMIT = re.compile(r"^submit", re.I)
START = re.compile(r"^(start|begin)", re.I)


class FlowError(Exception):
    pass


def _api_call(method: str, fragment: str) -> Callable[[Response], bool]:
    def matches(response: Response) -> bool:
        return response.request.method == method and fragment in response.url

    return matches


class Session:
    """One browser context (one respondent): cookies live only in memory."""

    def __init__(
        self,
        playwright: Playwright,
        redactor: Redactor,
        debug_dir: Optional[Path] = None,
    ) -> None:
        self.redactor = redactor
        self.debug_dir = debug_dir
        self.browser: Browser = playwright.chromium.launch(headless=True)
        self.context: BrowserContext = self.browser.new_context(
            locale="en-US",
            timezone_id="UTC",
            viewport={"width": 1280, "height": 900},
            # the page reports no analytics for the suite's visits
            extra_http_headers={"DNT": "1"},
        )
        self.context.set_default_timeout(STEP_TIMEOUT_MS)
        self.context.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        self.page: Page = self.context.new_page()

    def close(self) -> None:
        try:
            self.context.close()
        finally:
            self.browser.close()

    # -- debugging (local dry runs only) ---------------------------------------
    def dump(self, name: str) -> None:
        if not self.debug_dir:
            return
        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            snapshot = self.page.locator("body").aria_snapshot()
            (self.debug_dir / f"{name}.txt").write_text(
                self.redactor.scrub(f"{self.page.url}\n{snapshot}")
            )
        except Exception:
            pass

    # -- sign-in -----------------------------------------------------------------
    def sign_in(
        self,
        forms_base: str,
        workspace_id: str,
        redirect_path: str,
        address: str,
        read_code: Callable[[dt.datetime], str],
    ) -> None:
        """Respondent sign-in with an emailed code: one code is asked for,
        never more (rate limits); ``read_code`` waits for it."""
        page = self.page
        url = (
            f"{forms_base}/login?type=responder&workspace_id={quote(workspace_id)}"
            f"&redirect_to={quote(redirect_path)}"
        )
        page.goto(url)
        email = page.locator('input[type="email"]')
        email.wait_for(state="visible")
        email.fill(address)
        asked_at = dt.datetime.now(dt.timezone.utc)
        try:
            with page.expect_response(_api_call("POST", "/auth/otp/send")) as sent:
                email.press("Enter")
        except PlaywrightTimeout:
            self.dump("sign-in-send-timeout")
            raise FlowError("asking for a code got no answer the page could read")
        if sent.value.status != 200:
            self.dump("sign-in-send")
            raise FlowError(f"asking for a code answered {sent.value.status}")
        code_input = page.locator('form input:not([type="email"])').first
        code_input.wait_for(state="visible")
        code = read_code(asked_at)
        code_input.fill(code)
        try:
            with page.expect_response(
                _api_call("POST", "/auth/otp/validate")
            ) as checked:
                code_input.press("Enter")
        except PlaywrightTimeout:
            self.dump("sign-in-validate-timeout")
            raise FlowError("entering the code got no answer the page could read")
        if checked.value.status != 200:
            self.dump("sign-in-validate")
            raise FlowError(f"the code was refused ({checked.value.status})")

    # -- API calls with the session's cookies ------------------------------------
    def api(self, method: str, url: str, data: Optional[dict] = None):
        response = self.context.request.fetch(
            url,
            method=method,
            data=data,
            headers={"Accept": "application/json"},
            fail_on_status_code=False,
        )
        body = None
        try:
            body = response.json()
        except Exception:
            body = None
        return response.status, body

    # -- answering a form ------------------------------------------------------------
    def open_form(self, url: str, title: str) -> None:
        page = self.page
        page.goto(url)
        try:
            page.get_by_role("heading", name=title).first.wait_for(state="attached")
            start = page.get_by_role("button", name=START)
            question = page.locator("[data-question-wrapper]").first
            start.or_(question).first.wait_for(state="visible")
            if start.count() and start.first.is_visible():
                start.first.click()
            question.wait_for(state="visible")
        except PlaywrightTimeout:
            self.dump("open-form-timeout")
            raise FlowError("the form page did not show the form")

    def fill(self, answers: Mapping[str, str]) -> None:
        """Answer each field (by id) with its value: a choice is picked by its
        label, anything else typed."""
        for field_id, value in answers.items():
            wrapper = self.page.locator(f'[data-question-wrapper][id="{field_id}"]')
            wrapper.wait_for(state="visible")
            radio = wrapper.get_by_role("radio", name=value, exact=True)
            if radio.count():
                # a click, as a person would: some choice lists keep their
                # answer from the click, not from the input's checked state
                radio.first.click()
                continue
            box = wrapper.get_by_role("spinbutton").or_(wrapper.get_by_role("textbox"))
            box.first.fill(value)

    def share_identity(self) -> None:
        """A signed-in respondent shares their email with the response (the
        opt-in consent box above the submit button)."""
        box = self.page.locator('[data-testid="share-email-consent"]')
        box.first.wait_for(state="visible")
        box.first.check()

    def submit(self, form_id: str) -> dict:
        """Submit the form; the backend's answer to the submission."""
        page = self.page
        try:
            with page.expect_response(
                _api_call("POST", f"/forms/{form_id}/response")
            ) as done:
                page.get_by_role("button", name=SUBMIT).first.click()
        except PlaywrightTimeout:
            self.dump("submit-timeout")
            raise FlowError("the form did not submit (an answer was not accepted?)")
        if done.value.status not in (200, 201):
            self.dump("submit")
            raise FlowError(f"the submission answered {done.value.status}")
        try:
            body = done.value.json()
        except Exception:
            body = None
        return body if isinstance(body, dict) else {}

    # -- the respondent portal -----------------------------------------------------
    def request_deletion(self, forms_base: str, handle: str, response_id: str) -> None:
        page = self.page
        page.goto(
            f"{forms_base}/{quote(handle)}/submissions/{quote(response_id)}/settings"
        )
        ask = page.get_by_role("button", name=re.compile(r"deletion|delete", re.I))
        try:
            ask.first.wait_for(state="visible")
        except PlaywrightTimeout:
            self.dump("deletion-button")
            raise FlowError("the submission page offers no deletion request")
        ask.first.click()
        confirm = page.get_by_role("dialog").get_by_role(
            "button", name=re.compile(r"delet|request", re.I)
        )
        with page.expect_response(
            _api_call("DELETE", f"/submissions/{response_id}")
        ) as done:
            confirm.first.click()
        if done.value.status != 200:
            self.dump("deletion-request")
            raise FlowError(f"the deletion request answered {done.value.status}")

    def deletion_status_text(self, forms_base: str, handle: str, title: str) -> str:
        """The status the respondent sees for their request on ``title``'s
        response (the portal's deletion requests page)."""
        page = self.page
        page.goto(f"{forms_base}/{quote(handle)}/deletion-requests")
        card = page.get_by_text(title, exact=True).first
        try:
            card.wait_for(state="visible")
        except PlaywrightTimeout:
            self.dump("deletion-requests")
            raise FlowError("the request is not listed on the portal")
        status = page.get_by_text(
            re.compile(r"^(Not deleted:|Deleted \(|Deletion requested)")
        )
        status.first.wait_for(state="visible")
        return status.first.inner_text().strip()

    # -- a plain page ------------------------------------------------------------------
    def page_shows(self, url: str, title: str) -> int:
        """Load ``url``; the HTTP status, after waiting for ``title``."""
        response = self.page.goto(url)
        status = response.status if response else 0
        self.page.get_by_role("heading", name=title).first.wait_for(state="attached")
        return status
