#!/usr/bin/env python3
"""The HTTP side of scripts/upgrade-image-swap-check.sh (standard library only).

Talks to a throw-away stack over 127.0.0.1 and to its mail sink (Mailpit). Prints
one line per check, "PASS ...", "FAIL ...", "NOTCOVERED ..." or "INFO ...", which
the shell script counts. It never prints a secret, a sign-in code, a token, an
API key or the text of an answer.

    upgrade_swap_check_client.py <command> --api URL --mailpit URL --state FILE [...]

Commands (the shell runs them in this order):
    seed         old stack: creator sign-in, workspace, API key, a form with 3 responses
    readback     new stack: the seeded responses read through the API as they were
    webhook      new stack: private webhook addresses are refused; nothing is sent
    drafts       new stack: save and continue later (link mail, open, submit deletes)
    email        new stack: email action, team mail, copy only to a signed-in respondent
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# the production smoke suite's pure helpers: the standing form and its answers, and the
# reader of a code mail (reused, not copied)
sys.path.insert(0, str(Path(__file__).resolve().parent / "smoke"))
from smoke import forms as smoke_forms  # noqa: E402
from smoke.mail import (  # noqa: E402
    extract_code,
    newest_code_mail,
    parse_message,
)

ORIGIN = "http://localhost:3000"
OWNER = "swap-owner@example.com"
RESPONDENT = "swap-respondent@example.com"
TYPED_ADDRESS = "typed-in-an-answer@example.com"   # an address in an answer: never mailed
STARTED = time.monotonic()


def say(kind: str, text: str) -> None:
    print(f"{kind} {text}", flush=True)


def passed(what: str) -> None:
    say("PASS", what)


def failed(what: str, detail: str = "") -> None:
    say("FAIL", f"{what}{' (' + detail + ')' if detail else ''}")


def check(what: str, ok: bool, detail: str = "") -> bool:
    (passed(what) if ok else failed(what, detail))
    return ok


def info(text: str) -> None:
    say("INFO", text)


# --- a tiny HTTP session (cookies kept by hand: the stack is plain http) -------------------------------
class Sess:
    def __init__(self, base: str, bearer: str | None = None) -> None:
        self.base = base.rstrip("/")
        self.cookies: dict[str, str] = {}
        self.bearer = bearer

    def call(self, method: str, path: str, body=None, form: dict | None = None,
             expect: tuple[int, ...] | None = None, timeout: float = 60):
        headers = {"Origin": ORIGIN, "Accept": "application/json", "User-Agent": "bc-swapcheck/1"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        elif form is not None:
            boundary = "swap" + os.urandom(8).hex()
            data = "".join(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
                for k, v in form.items()
            ) .encode() + f"--{boundary}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        if self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        if self.bearer:
            headers["Authorization"] = f"Bearer {self.bearer}"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw, status, got = response.read(), response.status, response.headers
        except urllib.error.HTTPError as error:
            raw, status, got = error.read() or b"", error.code, error.headers
        for line in got.get_all("Set-Cookie") or []:
            pair = line.split(";", 1)[0]
            name, _, value = pair.partition("=")
            if value and "max-age=0" not in line.lower():
                self.cookies[name.strip()] = value.strip()
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = raw.decode(errors="replace")
        if expect is not None and status not in expect:
            code = parsed.get("code") if isinstance(parsed, dict) else ""
            raise RuntimeError(f"{method} {path.split('?')[0]} answered {status} {code or ''}".strip())
        return status, parsed


def code_of(body) -> str:
    """The error code of a refused call (ours: a short word, never a value)."""
    if isinstance(body, dict):
        for key in ("code", "detail"):
            value = body.get(key)
            if isinstance(value, str) and re.fullmatch(r"[a-z_0-9]{1,60}", value):
                return value
        problems = body.get("problems")
        if isinstance(problems, list) and problems and isinstance(problems[0], dict):
            return str(problems[0].get("code", ""))
    return ""


# --- the mail sink ------------------------------------------------------------------------------------------
class Mailpit:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def _get(self, path: str):
        with urllib.request.urlopen(self.base + path, timeout=30) as response:
            return json.loads(response.read())

    def to(self, address: str) -> list[dict]:
        query = urllib.parse.urlencode({"query": f'to:"{address}"', "limit": "50"})
        return self._get(f"/api/v1/search?{query}").get("messages", [])

    def message(self, message_id: str) -> dict:
        return self._get(f"/api/v1/message/{message_id}")

    def raw(self, message_id: str) -> bytes:
        with urllib.request.urlopen(f"{self.base}/api/v1/message/{message_id}/raw", timeout=30) as r:
            return r.read()

    def total(self) -> int:
        return int(self._get("/api/v1/messages?limit=1").get("messages_count", 0))

    def code_after(self, address: str, known: set, timeout: float = 60) -> str:
        """The code of the newest code mail to ``address`` that is not in ``known`` (the ids there
        were before the code was asked for: the reader's own clock-skew window would pick a stale one)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            messages = []
            for item in self.to(address):
                mid = str(item.get("ID", ""))
                if mid in known or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", mid):
                    continue
                messages.append(parse_message(mid, self.raw(mid)))
            newest = newest_code_mail(messages, address, dt.datetime.fromtimestamp(0, dt.timezone.utc))
            if newest is not None:
                try:
                    return extract_code(newest)
                except Exception:  # not a code mail (yet)
                    pass
            time.sleep(1.5)
        raise RuntimeError("no code mail arrived")

    def wait_mail(self, address: str, newer_than: int, timeout: float = 90) -> list[dict]:
        """The mails to ``address`` once there are more than ``newer_than`` of them."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = self.to(address)
            if len(found) > newer_than:
                return found
            time.sleep(2)
        return self.to(address)


def sign_in(base: str, mail: Mailpit, address: str, workspace_id: str | None = None) -> Sess:
    """A signed-in session: the code asked for and read from the mail sink (the respondent's
    sign-in is the workspace's, the creator's is the instance's)."""
    sess = Sess(base)
    known = {str(m.get("ID", "")) for m in mail.to(address)}
    query = urllib.parse.urlencode({"receiver_email": address})
    path = f"/workspaces/{workspace_id}/auth/otp/send" if workspace_id else "/auth/creator/otp/send"
    sess.call("POST", f"{path}?{query}", expect=(200,))
    code = mail.code_after(address, known)
    suffix = f"?workspace_id={workspace_id}" if workspace_id else ""
    sess.call("POST", f"/auth/otp/validate{suffix}", {"email": address, "otp_code": code}, expect=(200,))
    if not sess.cookies:
        raise RuntimeError("the sign-in set no cookie")
    return sess


# --- state ----------------------------------------------------------------------------------------------------
def load(path: str) -> dict:
    return json.loads(Path(path).read_text()) if Path(path).exists() else {}


def save(path: str, state: dict) -> None:
    Path(path).write_text(json.dumps(state))
    os.chmod(path, 0o600)


def standing_answers(given: dict) -> dict:
    return {
        "name": {"type": "text", "text": given["name"]},
        "about": {"type": "text", "text": given["about"]},
        "mail": {"type": "email", "email": given["mail"]},
        "count": {"type": "number", "number": int(given["count"])},
        "colour": {"type": "choice", "choice": {"value": smoke_forms.choice_id("colour", given["colour"])}},
        "agree": {"type": "boolean", "boolean": given["agree"] == "Yes"},
    }


def submit(base: str, workspace_id: str, form_id: str, answers: dict, sess: Sess | None = None, **fields):
    sess = sess or Sess(base)
    form = {"response": json.dumps({"answers": answers}), **fields}
    return sess.call("POST", f"/workspaces/{workspace_id}/forms/{form_id}/response", form=form)


def key_session(base: str, state: dict) -> Sess:
    return Sess(base + "/public/v1", bearer=state["api_key"])


def read_responses(key: Sess, form_id: str) -> list[dict]:
    _, listing = key.call("GET", f"/forms/{form_id}/responses?page=1&size=100", expect=(200,))
    out = []
    for item in listing.get("items", []):
        _, detail = key.call("GET", f"/forms/{form_id}/responses/{item['responseId']}", expect=(200,))
        out.append(detail)
    return out


def small_spec(title: str, trust: dict | None = None, extra_fields=()) -> dict:
    fields = [
        {"id": "name", "type": "short_text", "title": "Name"},
        {"id": "story", "type": "long_text", "title": "Story"},
        {"id": "mail", "type": "email", "title": "Email", "whyWeAsk": "Test data only."},
        *extra_fields,
    ]
    return {
        "specVersion": "1",
        "title": title,
        "language": "en",
        "pages": [{"id": "page-1", "fields": fields}],
        "endings": [{"title": "Thanks", "message": "Recorded."}],
        "trust": {"purpose": smoke_forms.PURPOSE, **(trust or {})},
    }


def create_form(key: Sess, spec: dict) -> tuple[str, str]:
    _, created = key.call("POST", "/forms", spec, expect=(201,))
    form_id = str(created["formId"])
    key.call("POST", f"/forms/{form_id}/publish", expect=(200,))
    return form_id, form_id


# --- commands --------------------------------------------------------------------------------------------------
def cmd_seed(args) -> None:
    state: dict = {"owner": OWNER}
    mail = Mailpit(args.mailpit)
    owner = sign_in(args.api, mail, OWNER)
    passed("the creator signed in with an emailed code (workspace created on the first sign-in)")
    _, mine = owner.call("GET", "/workspaces/mine", expect=(200,))
    workspace = mine[0]
    state["workspace_id"] = str(workspace["id"])
    owner.call("PATCH", f"/workspaces/{state['workspace_id']}", form={"title": "Swap check workspace"}, expect=(200,))
    _, key = owner.call(
        "POST", f"/workspaces/{state['workspace_id']}/api-keys",
        {"name": "swap check", "scopes": ["forms:read", "forms:write", "forms:delete", "responses:read"],
         "acknowledgeUnredactedResponses": True}, expect=(200, 201))
    state["api_key"] = key["token"]
    key_s = key_session(args.api, state)
    _, created = key_s.call("POST", "/forms", smoke_forms.standing_spec(), expect=(201,))
    state["form_id"] = str(created["formId"])
    key_s.call("POST", f"/forms/{state['form_id']}/publish", expect=(200,))
    for given in smoke_forms.STANDING_RESPONSES:
        status, _ = submit(args.api, state["workspace_id"], state["form_id"], standing_answers(given))
        if status != 200:
            failed("a seeded response was accepted", f"status {status}")
            return
    responses = read_responses(key_s, state["form_id"])
    problems = smoke_forms.compare_standing(responses)
    check("seeded: a workspace, a form with 6 questions and 3 responses read back through the API",
          len(responses) == 3 and not problems, "; ".join(problems))
    state["snapshot"] = {
        str(r["responseId"]): smoke_forms.answers_by_field(r.get("answers")) for r in responses
    }
    state["response_ids"] = sorted(state["snapshot"])
    save(args.state, state)
    # the ids the shell needs to queue the 4.1-style job
    print(f"IDS {state['workspace_id']} {state['form_id']} {state['response_ids'][0]}", flush=True)


def cmd_readback(args) -> None:
    state = load(args.state)
    key = key_session(args.api, state)
    responses = read_responses(key, state["form_id"])
    now = {str(r["responseId"]): smoke_forms.answers_by_field(r.get("answers")) for r in responses}
    check("the list answers with the same 3 responses (ids)", sorted(now) == state["response_ids"],
          f"{len(now)} found")
    check("every response's detail has the same answers as before the swap (decrypted)",
          now == state["snapshot"])
    problems = smoke_forms.compare_standing(responses)
    check("they still match the values they were given", not problems, "; ".join(problems))
    # the respondent-facing and staff reads too
    owner = sign_in(args.api, Mailpit(args.mailpit), OWNER)
    status, page = owner.call("GET", f"/workspaces/{state['workspace_id']}/forms/{state['form_id']}/submissions?size=20")
    total = len(page.get("items", [])) if isinstance(page, dict) else -1
    check("the workspace's own responses list (the webapp's read) shows them", status == 200 and total == 3,
          f"status {status}, {total} items")


def refused(sess: Sess, path: str, url: str, fields: list) -> tuple[int, str]:
    status, body = sess.call("POST", path, {"url": url, "fields": fields, "enabled": True})
    return status, code_of(body)


def cmd_webhook(args) -> None:
    state = load(args.state)
    mail = Mailpit(args.mailpit)
    owner = sign_in(args.api, mail, OWNER)
    ws, form = state["workspace_id"], state["form_id"]
    base = f"/workspaces/{ws}/forms/{form}/webhooks"
    status, variables = owner.call("GET", f"{base}/variables")
    sources = [v["source"] for v in (variables or []) if v.get("supported")][:2] if status == 200 else []
    check("the webhook switch is on (the variables are listed, not 422 webhooks_off)", status == 200 and bool(sources),
          f"status {status}")
    fields = [{"source": s, "key": f"q{i}"} for i, s in enumerate(sources)]
    targets = [
        ("a hostname that resolves to a private address of the docker network", args.receiver_url),
        ("a private IPv4 address", "https://10.0.0.1/hook"),
        ("the cloud metadata address", "https://169.254.169.254/latest/meta-data/"),
        ("loopback", "https://127.0.0.1/hook"),
        ("plain http", "http://example.com/hook"),
        ("a port other than 443", "https://example.com:8443/hook"),
    ]
    for what, url in targets:
        status, code = refused(owner, base, url, fields)
        check(f"the SSRF guard refuses {what} (422)", status == 422, f"status {status} code {code}")
        info(f"  {what}: {status} {code}")
    status, listing = owner.call("GET", base)
    check("no webhook was stored by those attempts", status == 200 and listing == [], f"status {status}")
    # a response is submitted: nothing is sent anywhere
    given = smoke_forms.STANDING_RESPONSES[0]
    submit(args.api, ws, form, standing_answers(given))
    time.sleep(12)
    say("NOTCOVERED", "a webhook delivery arrives signed (X-Bettercollected-Signature): the guard has no setting that "
        "allows a private destination (docs/webhooks.md: \"There is no setting that relaxes them, and no plain-http "
        "mode\"), so a receiver in this stack cannot be registered. Goes on the production smoke list "
        "(release checklist: one delivery to an allowed public https endpoint with a valid signature).")


def cmd_drafts(args) -> None:
    state = load(args.state)
    mail = Mailpit(args.mailpit)
    owner = sign_in(args.api, mail, OWNER)
    key = key_session(args.api, state)
    ws = state["workspace_id"]
    status, _ = Sess(args.api).call("GET", "/providers")
    # a form that keeps drafts
    title = "Swap draft form " + uuid.uuid4().hex[:6]
    form_id, _ = create_form(key, small_spec(title, {"allowSaveDraft": True, "draftRetentionDays": 7}))
    state["draft_form_id"] = form_id
    save(args.state, state)
    check("a form with allow_save_draft was created and published (the switch lets it on)", True)
    base = f"/workspaces/{ws}/forms/{form_id}/drafts"
    anon = Sess(args.api)
    saved_answers = {
        "name": {"type": "text", "text": "Draft Respondent"},
        "story": {"type": "text", "text": "A synthetic half-finished story."},
    }
    address = "draft-respondent@example.com"
    before = len(mail.to(address))
    status, body = anon.call("POST", f"{base}/link", {
        "answers": saved_answers, "hiddenFields": {}, "position": {"pageId": "page-1", "history": []},
        "email": address,
    })
    check("anonymous 'save and continue later' is accepted (200, an edit key comes back)",
          status == 200 and isinstance(body, dict) and bool(body.get("editKey")), f"status {status} {code_of(body)}")
    if status != 200:
        return
    found = mail.wait_mail(address, before)
    check("the link mail reached the sink", len(found) > before)
    if len(found) <= before:
        return
    message = mail.message(str(found[0]["ID"]))
    text, html_part, subject = message.get("Text", ""), message.get("HTML", ""), message.get("Subject", "")
    token_match = re.search(r"#resume=([0-9a-f]{24}\.[A-Za-z0-9_-]{43})", text + " " + html_part)
    check("the mail carries the resume link with its token", token_match is not None)
    visible = text + " " + re.sub(r"<[^>]+>", " ", html_part) + " " + subject
    leaked = [w for w in ("Draft Respondent", "half-finished", title) if w in visible]
    check("the mail holds no answer and no form title (fixed wording and the link only)", not leaked,
          f"{len(leaked)} of them found")
    links = set(re.findall(r"https?://[^\s\"'<>)]+", text))
    info(f"  the mail's subject is '{subject}', its text has {len(text.split())} words and {len(links)} distinct link(s)")
    if token_match is None:
        return
    token = token_match.group(1)
    status, opened = Sess(args.api).call("POST", f"{base}/open", {"token": token})
    got = smoke_forms.answers_by_field((opened or {}).get("answers")) if status == 200 else {}
    check("opening the link (POST .../open with the token from the mail) returns the saved answers",
          status == 200 and got == smoke_forms.answers_by_field(saved_answers), f"status {status} {code_of(opened)}")
    # submitting finishes the draft: the draft is deleted
    status, _ = submit(args.api, ws, form_id, {**saved_answers, "mail": {"type": "email", "email": address}},
                       draft_key=token)
    check("submitting the form with the draft's token is accepted", status == 200, f"status {status}")
    status, gone = Sess(args.api).call("POST", f"{base}/open", {"token": token})
    check("the draft is gone after the submit (the same link now answers 404)", status == 404,
          f"status {status} {code_of(gone)}")
    state["draft_address"] = address
    save(args.state, state)


def cmd_email(args) -> None:
    state = load(args.state)
    mail = Mailpit(args.mailpit)
    owner = sign_in(args.api, mail, OWNER)
    key = key_session(args.api, state)
    ws = state["workspace_id"]
    title = "Swap email form " + uuid.uuid4().hex[:6]
    form_id, _ = create_form(key, small_spec(title))
    base = f"/workspaces/{ws}/forms/{form_id}/email-actions"
    _, variables = owner.call("GET", f"{base}/variables", expect=(200,))
    by_label = {v["label"]: v["source"] for v in variables if v.get("supported")}
    fields = [{"source": by_label[l], "key": k} for l, k in (("Name", "name"), ("Story", "story")) if l in by_label]
    check("the email-action variables list the form's questions", len(fields) == 2, f"labels {sorted(by_label)}")
    status, action = owner.call("POST", base, {
        "name": "Swap check", "enabled": True, "fields": fields,
        "en": {"subject": "Swapcheck team mail: {{name}}", "body": "New response from {{name}}.\n\n{{answers}}"},
        "nl": {"subject": "Swapcheck teammail: {{name}}", "body": "Nieuwe reactie van {{name}}.\n\n{{answers}}"},
        "teamRecipients": [OWNER], "respondentCopy": True,
    })
    check("an email action with a team recipient (a member of the workspace) and the respondent copy on was created",
          status == 201, f"status {status} {code_of(action)}")
    if status != 201:
        return
    # 1. a signed-in respondent
    resp = sign_in(args.api, mail, RESPONDENT, workspace_id=ws)
    team_before, copy_before = len(mail.to(OWNER)), len(mail.to(RESPONDENT))
    status, _ = submit(args.api, ws, form_id, {
        "name": {"type": "text", "text": "Signed In Sam"},
        "story": {"type": "text", "text": "Written while signed in."},
        "mail": {"type": "email", "email": TYPED_ADDRESS},
    }, sess=resp)
    check("a signed-in respondent's submission is accepted", status == 200, f"status {status}")
    team = mail.wait_mail(OWNER, team_before)
    copy = mail.wait_mail(RESPONDENT, copy_before)
    team_new = [m for m in team if "Swapcheck team mail: Signed In Sam" in m.get("Subject", "")]
    check("mailpit received the team mail (to the workspace member)", len(team_new) == 1, f"{len(team_new)} found")
    check("mailpit received the respondent's copy at the account's own address", len(copy) == copy_before + 1,
          f"{len(copy) - copy_before} new")
    if len(copy) > copy_before:
        m = mail.message(str(copy[0]["ID"]))
        info(f"  the copy's subject: '{m.get('Subject', '')}'")
        check("the copy is the fixed-wording mail (no form title, not the creator's template)",
              title not in (m.get("Text", "") + m.get("Subject", "")) and "Swapcheck" not in m.get("Subject", ""))
    check("nothing was sent to the address typed into an answer", len(mail.to(TYPED_ADDRESS)) == 0)
    # 2. anonymous
    team_before, copy_before, total_before = len(mail.to(OWNER)), len(mail.to(RESPONDENT)), mail.total()
    status, _ = submit(args.api, ws, form_id, {
        "name": {"type": "text", "text": "Anonymous Ann"},
        "story": {"type": "text", "text": "Written without signing in."},
        "mail": {"type": "email", "email": TYPED_ADDRESS},
    })
    check("an anonymous submission is accepted", status == 200, f"status {status}")
    team = mail.wait_mail(OWNER, team_before)
    check("the team mail arrives for the anonymous submission",
          len([m for m in team if "Swapcheck team mail: Anonymous Ann" in m.get("Subject", "")]) == 1)
    time.sleep(20)   # a copy would be queued with it: give it the time the team mail needed, and more
    check("no copy was sent for the anonymous submission (nothing to the typed address, nothing new to the account)",
          len(mail.to(TYPED_ADDRESS)) == 0 and len(mail.to(RESPONDENT)) == copy_before and mail.total() == total_before + 1,
          f"typed {len(mail.to(TYPED_ADDRESS))}, account +{len(mail.to(RESPONDENT)) - copy_before}, "
          f"all +{mail.total() - total_before}")
    status, log = owner.call("GET", f"{base}/deliveries?limit=50")
    rows = log.get("items", log) if isinstance(log, dict) else (log or [])
    kinds = sorted(f"{r.get('channel')}:{r.get('status')}:{r.get('error') or r.get('code') or ''}" for r in rows)
    info(f"  the delivery log (channel:status:code): {', '.join(kinds)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["seed", "readback", "webhook", "drafts", "email"])
    parser.add_argument("--api", required=True)
    parser.add_argument("--mailpit", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--receiver-url", default="https://hook.example.com/hook")
    args = parser.parse_args()
    try:
        {"seed": cmd_seed, "readback": cmd_readback, "webhook": cmd_webhook,
         "drafts": cmd_drafts, "email": cmd_email}[args.command](args)
    except Exception as error:  # a harness or product failure: reported, never a traceback with values
        failed(f"{args.command} stopped", f"{type(error).__name__}: {str(error)[:200]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
