"""Scripted HTTP client of scripts/v4-compose-check.sh: the admin portal's first-run
wizard, the email-code + authenticator sign-in, the read-only pages and a task run,
exactly as a browser would drive them (no JavaScript is needed anywhere).

Standard library only. Run it with `uv run --no-project python -I scripts/v4_check_client.py ...`
(the check script does). It prints one line per check, `PASS <what>` or
`FAIL <what> (<detail>)`, plus `INFO name=value` lines for values the shell needs
(a fingerprint, a task state). It never prints a token, a code, a cookie, a
secret or a form value: statuses, counts and names only. The setup token comes in
through the environment (V4_SETUP_TOKEN), never the command line.

Commands (all take --base http://127.0.0.1:PORT --state FILE):
  wizard    --email E --mailpit URL --mail-server HOST --mail-port N [--fingerprint FP]
  signin    --email E --mailpit URL
  pages     [--expect-services a,b,c]
  task      --task NAME [--param name=value ...] [--timeout SECONDS]
  negatives                      (requests the gate and the wizard must answer with a bare 404)
The state file (mode 600) holds the authenticator secret and the session between commands.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import html
import http.client
import json
import os
import re
import struct
import sys
import time
import urllib.parse
from pathlib import Path

UA = "bc-v4-acceptance/1"
FAILS = 0


def say(kind: str, text: str) -> None:
    print(f"{kind} {text}", flush=True)


def passed(what: str) -> None:
    say("PASS", what)


def failed(what: str, detail: str = "") -> None:
    global FAILS
    FAILS += 1
    say("FAIL", f"{what} ({detail})" if detail else what)


def check(what: str, ok: bool, detail: str = "") -> bool:
    (passed if ok else lambda w: failed(w, detail))(what)
    return ok


# --- RFC 6238 (SHA-1, 6 digits, 30 s) ---------------------------------------------------------


def hotp(secret_b32: str, counter: int, digits: int = 6) -> str:
    cleaned = re.sub(r"\s+", "", secret_b32).upper()
    key = base64.b32decode(cleaned + "=" * (-len(cleaned) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**digits).zfill(digits)


def self_test() -> None:
    """RFC 6238 appendix B vectors (SHA-1 secret "12345678901234567890", 8 digits)."""
    secret = base64.b32encode(b"12345678901234567890").decode()
    for moment, want in ((59, "94287082"), (1111111109, "07081804"), (20000000000, "65353130")):
        got = hotp(secret, moment // 30, 8)
        if got != want:
            raise SystemExit(f"TOTP helper is wrong at {moment}")


# --- state ----------------------------------------------------------------------------------------


class State:
    def __init__(self, path: str | None) -> None:
        self.path = Path(path) if path else None
        self.data = {"totp": "", "last_counter": 0, "cookies": {}}
        if self.path and self.path.exists():
            self.data.update(json.loads(self.path.read_text()))

    def save(self) -> None:
        if self.path is None:
            return
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(self.data, handle)

    def next_code(self) -> str:
        """A code for a step not used before: a code works once, and one step of
        drift either way is accepted, so the next step's is used at once."""
        now = int(time.time() // 30)
        counter = max(now, int(self.data["last_counter"]) + 1)
        if counter > now + 1:
            time.sleep(max(0.0, (counter - 1) * 30 - time.time()) + 1)
        self.data["last_counter"] = counter
        self.save()
        return hotp(self.data["totp"], counter)


# --- the browser ----------------------------------------------------------------------------------


class Response:
    def __init__(self, status: int, headers: dict, body: str) -> None:
        self.status, self.headers, self.body = status, headers, body

    @property
    def location(self) -> str:
        return self.headers.get("location", "")


class Browser:
    """One HTTP client with a cookie jar that ignores the `Secure` flag (the
    portal is reached over plain HTTP on the loopback through the SSH-tunnel
    address; a browser would do the same on localhost)."""

    def __init__(self, base: str, state: State) -> None:
        parsed = urllib.parse.urlparse(base)
        self.host, self.port = parsed.hostname, parsed.port
        self.origin = f"http://{parsed.hostname}:{parsed.port}"
        self.state = state

    @property
    def cookies(self) -> dict:
        return self.state.data["cookies"]

    def request(self, method: str, path: str, form: dict | None = None, extra: dict | None = None,
                body: bytes | None = None) -> Response:
        headers = {"User-Agent": UA, "Accept": "text/html,application/json"}
        if self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        data = body
        if method == "POST":
            headers["Origin"] = self.origin
            headers["Sec-Fetch-Site"] = "same-origin"
            if form is not None:
                data = urllib.parse.urlencode(form).encode()
                headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers.update(extra or {})
        conn = http.client.HTTPConnection(self.host, self.port, timeout=20)
        try:
            conn.request(method, path, body=data, headers=headers)
            raw = conn.getresponse()
            text = raw.read().decode("utf-8", "replace")
            lowered = {k.lower(): v for k, v in raw.getheaders()}
            for line in raw.msg.get_all("Set-Cookie") or []:
                name, _, rest = line.partition("=")
                value, _, attrs = rest.partition(";")
                if value == "" or "max-age=0" in attrs.lower():
                    self.cookies.pop(name, None)
                else:
                    self.cookies[name] = value
            self.state.save()
            return Response(raw.status, lowered, text)
        finally:
            conn.close()

    def get(self, path: str) -> Response:
        return self.request("GET", path)

    def post(self, path: str, form: dict) -> Response:
        return self.request("POST", path, form)

    def follow(self, response: Response, limit: int = 6) -> Response:
        while response.status in (301, 302, 303, 307) and limit > 0:
            response = self.get(response.location)
            limit -= 1
        return response


def csrf_of(page: Response) -> str:
    found = re.search(r'name="csrf_token" value="([^"]+)"', page.body)
    return html.unescape(found.group(1)) if found else ""


def page_notes(page: Response) -> list:
    """The error and notice lines of a page (fixed texts: the portal never echoes a typed value)."""
    return [html.unescape(t).strip()[:120] for t in re.findall(r'<p class="(?:error|notice[^"]*)"[^>]*>([^<]+)</p>', page.body)][:4]


def form_defaults(page: Response, action: str) -> dict:
    """The fields a browser would send for the form that posts to `action`."""
    for chunk in re.split(r"(?=<form )", page.body):
        if f'action="{action}"' not in chunk[:300]:
            continue
        chunk = chunk.split("</form>")[0]
        fields: dict = {}
        for tag in re.findall(r"<input\b[^>]*>", chunk):
            name = re.search(r'name="([^"]+)"', tag)
            if not name:
                continue
            kind = (re.search(r'type="([^"]+)"', tag) or [None, "text"])[1]
            value = re.search(r'value="([^"]*)"', tag)
            if kind == "checkbox":
                if " checked" in tag:
                    fields[name.group(1)] = html.unescape(value.group(1)) if value else "on"
            elif kind != "submit":
                fields[name.group(1)] = html.unescape(value.group(1)) if value else ""
        for select in re.finditer(r'<select\b[^>]*name="([^"]+)"[^>]*>(.*?)</select>', chunk, re.S):
            options = re.findall(r'<option value="([^"]*)"([^>]*)>', select.group(2))
            chosen = next((v for v, rest in options if "selected" in rest), options[0][0] if options else "")
            fields[select.group(1)] = html.unescape(chosen)
        for area in re.finditer(r'<textarea\b[^>]*name="([^"]+)"', chunk):
            fields[area.group(1)] = ""
        return fields
    return {}


# --- the mail sink (mailpit) ----------------------------------------------------------------------


class Sink:
    def __init__(self, base: str) -> None:
        parsed = urllib.parse.urlparse(base)
        self.host, self.port = parsed.hostname, parsed.port

    def _get(self, path: str) -> dict:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=10)
        try:
            conn.request("GET", path)
            return json.loads(conn.getresponse().read().decode())
        finally:
            conn.close()

    def count(self) -> int:
        return int(self._get("/api/v1/messages?limit=1").get("messages_count", 0))

    def mails_to(self, address: str) -> list:
        listing = self._get("/api/v1/messages?limit=200")
        return [m for m in listing.get("messages", [])
                if any(t.get("Address", "").lower() == address.lower() for t in m.get("To", []))]

    def code_after(self, before: int, address: str, digits: int, timeout: float = 60.0) -> str:
        """The code in the newest mail to `address` that arrived after `before` mails."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            listing = self._get("/api/v1/messages?limit=50")
            for message in listing.get("messages", []):
                if not any(t.get("Address", "").lower() == address.lower() for t in message.get("To", [])):
                    continue
                if listing.get("messages_count", 0) <= before:
                    continue
                body = self._get(f"/api/v1/message/{message['ID']}").get("Text", "")
                found = re.search(rf"(?<!\d)(\d{{{digits}}})(?!\d)", body)
                if found:
                    return found.group(1)
            time.sleep(1)
        return ""


# --- commands -------------------------------------------------------------------------------------


def stepup(browser: Browser, page_path: str) -> None:
    """Answer the step-up prompt with a fresh authenticator code."""
    prompt = browser.get(f"/mfa/stepup?next={page_path}")
    browser.post("/mfa/stepup", {"csrf_token": csrf_of(prompt), "next": page_path, "code": browser.state.next_code()})


def cmd_negatives(browser: Browser, args) -> None:
    """Nothing here reveals the portal or the wizard to someone without the right to see it."""
    for path in ("/nope", "/admin", "/api/audit", "/health", "/config", "/tasks"):  # a JSON path may answer 401
        page = browser.get(path)
        bare = page.status in (401, 404, 303) and "secret" not in page.body.lower()
        check(f"signed-out {path} answers a redirect to sign-in or a bare 404", bare, f"status {page.status}")
    wrong_host = browser.request("GET", "/login", extra={"Host": "attacker.example:80"})
    check("a request with a Host outside the allowlist gets a bare 404", wrong_host.status == 404 and len(wrong_host.body) < 40,
          f"status {wrong_host.status}")


def cmd_wizard(browser: Browser, args) -> None:
    token = os.environ.get("V4_SETUP_TOKEN", "")
    email = args.email
    sink = Sink(args.mailpit)
    page = browser.get("/setup")
    if not check("/setup shows the token form on a new install", page.status == 200 and 'name="token"' in page.body, f"status {page.status}"):
        return
    # a wrong token and an unlisted address look exactly alike (status, redirect, page)
    wrong_token = browser.post("/setup", {"csrf_token": csrf_of(page), "token": "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH", "email": email})
    page = browser.get("/setup")
    wrong_address = browser.post("/setup", {"csrf_token": csrf_of(page), "token": token, "email": "stranger@example.com"})
    same = (wrong_token.status, wrong_token.location) == (wrong_address.status, wrong_address.location)
    check("wrong token and wrong address are answered identically", same and wrong_token.location.startswith("/setup"),
          f"{wrong_token.status} {wrong_token.location!r} vs {wrong_address.status} {wrong_address.location!r}")
    after_token, after_address = browser.follow(wrong_token), browser.follow(wrong_address)
    strip = lambda r: re.sub(r'value="[^"]*"', "", r.body)  # noqa: E731 - the CSRF values differ
    check("the pages shown after either refusal are identical", strip(after_token) == strip(after_address))
    check("neither refusal started a session", "__Host-bcadmin" not in browser.cookies)

    page = browser.get("/setup")
    right = browser.post("/setup", {"csrf_token": csrf_of(page), "token": token, "email": email})
    if not check("the right token and address start the setup session", right.status == 303 and right.location == "/mfa/enrol"
                 and "__Host-bcadmin" in browser.cookies, f"{right.status} {right.location!r}"):
        return

    enrol = browser.get("/mfa/enrol")
    started = browser.post("/mfa/enrol", {"csrf_token": csrf_of(enrol)})
    secret = re.search(r'class="secret">([^<]+)<', started.body)
    factor = re.search(r'name="factor_id" value="([^"]+)"', started.body)
    if not check("enrolment shows a setup key", bool(secret and factor), f"status {started.status}"):
        return
    browser.state.data["totp"] = html.unescape(secret.group(1)).strip()
    browser.state.save()
    # a wrong code first: refused, nothing enrolled
    wrong = browser.post("/mfa/enrol/confirm", {"csrf_token": csrf_of(started), "factor_id": factor.group(1), "code": "000000"})
    check("a wrong authenticator code does not enrol", wrong.status == 200 and "recovery" not in wrong.body.lower().split("<main")[-1][:400])
    started = browser.post("/mfa/enrol", {"csrf_token": csrf_of(browser.get("/mfa/enrol"))}) if "factor_id" not in wrong.body else wrong
    factor = re.search(r'name="factor_id" value="([^"]+)"', started.body)
    secret = re.search(r'class="secret">([^<]+)<', started.body)
    if secret:  # the refused page never shows a secret twice; a restart made a new one
        browser.state.data["totp"] = html.unescape(secret.group(1)).strip()
        browser.state.save()
    confirm = browser.post("/mfa/enrol/confirm", {
        "csrf_token": csrf_of(started), "factor_id": factor.group(1) if factor else "", "code": browser.state.next_code()})
    codes = re.findall(r"<li[^>]*><code[^>]*>([^<]+)</code>", confirm.body)
    if not check("a correct authenticator code enrols and shows ten recovery codes", confirm.status == 200 and len(codes) == 10,
                 f"status {confirm.status}, {len(codes)} codes"):
        return
    saved = browser.post("/mfa/recovery-codes/saved", {"csrf_token": csrf_of(confirm), "saved": "yes"})
    page = browser.follow(saved)
    check("after enrolment the wizard continues with the mail step", page.status == 200 and "/setup/mail" in (saved.location + page.body), f"{saved.status} {saved.location!r}")

    # mail: test against the sink, save only after the code from the mail is typed
    before = sink.count()
    mail_form = {"server": args.mail_server, "port": str(args.mail_port), "sender": "portal@example.com", "user": "", "password": "",
                 "starttls": "false", "ssl_tls": "false", "use_credentials": "false", "validate_certs": "false"}
    page = browser.get("/setup/mail")
    posted = browser.post("/setup/mail/test", {"csrf_token": csrf_of(page), **mail_form})
    if posted.status == 303 and "stepup" in posted.location:
        stepup(browser, "/setup/mail")
        page = browser.get("/setup/mail")
        posted = browser.post("/setup/mail/test", {"csrf_token": csrf_of(page), **mail_form})
    pending = re.search(r'name="pending" value="([^"]+)"', posted.body)
    if not check("the mail test is sent to the admin's own address", posted.status == 200 and bool(pending), f"status {posted.status}; {page_notes(posted)}"):
        return
    mail_code = sink.code_after(before, email, 6)
    if not check("the test mail arrived in the sink with a six-digit code", bool(mail_code)):
        return
    pending_value = html.unescape(pending.group(1))
    bad = browser.post("/setup/mail/confirm", {"csrf_token": csrf_of(posted), "pending": pending_value, "mail_code": "000000", "code": ""})
    check("a wrong mail code saves nothing and asks again", bad.status == 200 and bad.location == "", f"status {bad.status}")
    done = browser.post("/setup/mail/confirm", {"csrf_token": csrf_of(posted), "pending": pending_value, "mail_code": mail_code, "code": ""})
    if done.status == 200 and "action=\"/setup/mail/confirm\"" in done.body:  # a fresh factor code is asked for
        done = browser.post("/setup/mail/confirm", {"csrf_token": csrf_of(done), "pending": pending_value,
                                                    "mail_code": mail_code, "code": browser.state.next_code()})
    check("the right mail code saves the settings and leads to the last step", done.status == 303 and done.location == "/setup/finish",
          f"{done.status} {done.location!r}")

    finish = browser.get("/setup/finish")
    shown = re.search(r'class="secret">([^<]+)<', finish.body)
    check("the last step shows the master key fingerprint", bool(shown) and finish.status == 200)
    if args.fingerprint and shown:
        check("it is the fingerprint deploy.sh printed", html.unescape(shown.group(1)).strip() == args.fingerprint)
    no_ack = browser.post("/setup/finish", {"csrf_token": csrf_of(finish)})
    check("finishing without the acknowledgement is refused", no_ack.status == 400)
    closed = browser.post("/setup/finish", {"csrf_token": csrf_of(finish), "ack": "yes"})
    check("acknowledging closes the wizard", closed.status == 303 and closed.location == "/", f"{closed.status} {closed.location!r}")

    anon = Browser(f"http://{browser.host}:{browser.port}", State(None))
    gone = anon.get("/setup")
    check("/setup is a bare 404 afterwards", gone.status == 404 and len(gone.body) < 40, f"status {gone.status}")
    gone = anon.post("/setup", {"token": token, "email": email})
    nope = anon.post("/nope", {"token": token, "email": email})
    # a POST to /setup is the one wizard route that answers (a redirect back to /setup, which is a 404 now);
    # without a CSRF token it is refused first. Either way: no page, no session, no body
    check("a POST to /setup after the wizard gets no page and no session (status 403, or a redirect to the 404)",
          gone.status in (403, 404) or (gone.status == 303 and gone.location.startswith("/setup")),
          f"status {gone.status}, a POST to a path that does not exist: {nope.status}")
    check("and no session cookie", "__Host-bcadmin" not in anon.cookies and len(gone.body) < 40)
    gone = browser.get("/setup/mail")
    check("/setup/mail is gone for the signed-in admin too", gone.status == 404, f"status {gone.status}")


def cmd_signin(browser: Browser, args) -> None:
    sink = Sink(args.mailpit)
    page = browser.get("/")
    if page.status == 200 and "Sign out" in page.body:  # sign out first, as a returning admin would
        out = browser.post("/logout", {"csrf_token": csrf_of(page)})
        check("sign out ends the session", out.status in (302, 303), f"status {out.status}")
    browser.cookies.clear()
    # an unlisted address is answered like a listed one, and no mail is sent to it
    before = sink.count()
    page = browser.get("/login")
    stranger = browser.post("/login", {"csrf_token": csrf_of(page), "email": "stranger@example.com"})
    check("an address that is not an admin gets the same answer", stranger.status == 303 and stranger.location == "/login/code")
    time.sleep(2)
    check("and no mail is sent to it", not sink.mails_to("stranger@example.com"))
    browser.cookies.clear()
    page = browser.get("/login")
    before = sink.count()
    posted = browser.post("/login", {"csrf_token": csrf_of(page), "email": args.email})
    check("sign-in asks for the emailed code", posted.status == 303 and posted.location == "/login/code")
    code = sink.code_after(before, args.email, 8)
    if not check("the sign-in mail arrived with an eight-digit code", bool(code)):
        return
    page = browser.get("/login/code")
    wrong = browser.post("/login/code", {"csrf_token": csrf_of(page), "code": "00000000"})
    check("a wrong email code is refused", wrong.status == 200)
    page = browser.get("/login/code")
    entered = browser.post("/login/code", {"csrf_token": csrf_of(page), "code": code})
    check("the right email code leads to the second factor", entered.status == 303 and entered.location == "/mfa", f"{entered.status} {entered.location!r}")
    verify = browser.follow(entered)
    check("the second factor is asked for", verify.status == 200 and 'action="/mfa/verify"' in verify.body)
    blocked = browser.get("/health")
    check("nothing else is reachable before the second factor", blocked.status in (303, 404))
    done = browser.post("/mfa/verify", {"csrf_token": csrf_of(verify), "code": browser.state.next_code()})
    check("the authenticator code completes the sign-in", done.status == 303 and done.location == "/", f"{done.status} {done.location!r}")


def cmd_pages(browser: Browser, args) -> None:
    for path in ("/", "/health", "/config", "/audit", "/settings", "/tasks", "/tasks/runs", "/metrics", "/sessions"):
        page = browser.get(path)
        check(f"GET {path} answers 200", page.status == 200, f"status {page.status}")
    health = browser.get("/health").body
    names = re.findall(r'<th scope="row">([a-z0-9-]+)</th><td>[^<]*</td>\s*<td><span class="(?:ok|bad)">(reporting|stopped)</span>', health)
    reporting = sorted({name for name, state in names if state == "reporting"})
    # an instance row that went quiet (the container before a restart) is "stopped" next to the
    # live one of the same service: only a service with no live instance counts as down
    stopped = sorted({name for name, state in names if state == "stopped"} - set(reporting))
    say("INFO", "health rows: " + ", ".join(f"{n}={st}" for n, st in names))
    expected = [s for s in (args.expect_services or "").split(",") if s]
    check("/health: every expected service reports (" + ",".join(expected) + ")", all(s in reporting for s in expected),
          f"reporting {reporting}")
    check("/health: no service is down (no live instance)", not stopped, f"stopped {stopped}")
    check("/health: the admin schema is current", re.search(r'<th scope="row">admin</th>\s*<td><span class="ok">current</span>', health) is not None)
    check("/health: the database is reachable", 'class="ok">Reachable' in health)
    config = browser.get("/config").body
    check("/config lists the registry and the super admin", "PLATFORM_ADMIN_EMAILS" in config or "Super admin" in config or "super admin" in config)
    audit = browser.get("/audit").body
    check("/audit shows the setup and sign-in rows", "signin" in audit and "setup" in audit)
    metrics = browser.get("/metrics")
    check("/metrics renders", metrics.status == 200)
    for path in ("/api/audit?limit=5",):
        check(f"GET {path} answers 200 JSON", browser.get(path).status == 200)


def cmd_task(browser: Browser, args) -> None:
    page = browser.get(f"/tasks/{args.task}")
    if not check(f"/tasks/{args.task} shows the task form", page.status == 200, f"status {page.status}"):
        return
    fields = form_defaults(page, f"/tasks/{args.task}/dry-run")
    fields.update({"csrf_token": csrf_of(page)})
    for item in args.param or []:
        name, _, value = item.partition("=")
        fields["p_" + name] = value  # the portal's task forms prefix every parameter with p_
    started = browser.post(f"/tasks/{args.task}/dry-run", fields)
    run_id = re.match(r"^/tasks/runs/([0-9a-f-]{36})", started.location or "")
    if not check("the dry run is accepted and signed into a run", started.status == 303 and bool(run_id), f"{started.status} {started.location!r}"):
        return
    deadline = time.time() + args.timeout
    state, payload = "", {}
    while time.time() < deadline:
        poll = browser.get(f"/api/tasks/runs/{run_id.group(1)}?after=0")
        if poll.status == 200:
            payload = json.loads(poll.body)
            state = payload.get("state", "")
            if payload.get("terminal"):
                break
        time.sleep(1.5)
    say("INFO", f"task_state={state}")
    say("INFO", f"task_refusal={payload.get('refusal_code') or ''}")
    for event in payload.get("events", []):
        counts = ",".join(f"{k}={v}" for k, v in sorted(event.get("counts", {}).items()) if isinstance(v, int))
        say("INFO", f"task_event={event.get('code')} {counts}".strip())
    check("the task runner executed the run to a terminal state", bool(payload.get("terminal")), f"state {state!r}")
    page = browser.get(f"/tasks/runs/{run_id.group(1)}")
    check("the run page renders", page.status == 200)


COMMANDS = {"wizard": cmd_wizard, "signin": cmd_signin, "pages": cmd_pages, "task": cmd_task, "negatives": cmd_negatives}


def main() -> int:
    self_test()
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--base", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--email", default="")
    parser.add_argument("--mailpit", default="")
    parser.add_argument("--mail-server", default="")
    parser.add_argument("--mail-port", type=int, default=1025)
    parser.add_argument("--fingerprint", default="")
    parser.add_argument("--expect-services", default="")
    parser.add_argument("--task", default="")
    parser.add_argument("--param", action="append")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    state = State(args.state)
    browser = Browser(args.base, state)
    COMMANDS[args.command](browser, args)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
