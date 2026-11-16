#!/usr/bin/env python3
"""Contract test: the same requests to the Python backend and to bc-api, one database.

    python3 rust/contract/contract_test.py FIXTURE.json PYTHON_URL RUST_URL [--subset] [--report OUT.json]

FIXTURE.json is written by seed.py (ids and throw-away tokens). Both servers must
run against the database seed.py seeded, with the same AUTH_JWT_SECRET ring and the
same feature switches. Every case is sent to both; status, headers (all but a few
transport ones) and the body bytes are compared. A case where bc-api answers 501
"needs the Python backend" is reported as DELEGATED, not as a difference: the
deployed design proxies those requests (session refresh, single sign-on policy).
Exit status 0 only when there is no difference.
"""

import http.client
import json
import sys
from urllib.parse import urlsplit

IGNORED = {"date", "server", "connection", "keep-alive", "transfer-encoding"}
HOST = "contract.test"


def call(base, method, path, headers):
    parts = urlsplit(base)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=15)
    send = {"Host": HOST}
    send.update(headers)
    conn.request(method, path, headers=send)
    response = conn.getresponse()
    body = response.read()
    heads = {}
    for name, value in response.getheaders():
        name = name.lower()
        if name in IGNORED:
            continue
        heads.setdefault(name, []).append(value)
    conn.close()
    return response.status, {k: sorted(v) for k, v in heads.items()}, body


def cookie(**pairs):
    return "; ".join(f"{k}={v}" for k, v in pairs.items())


def build(fx, subset):
    ws, tok, people = fx["workspaces"], fx["tokens"], fx["people"]
    cases = []

    def add(name, method, path, headers=None):
        cases.append((name, method, path, headers or {}))

    def perm(w):
        return f"/api/v1/workspaces/{w}/permissions"

    def auth(name_or_token):
        t = tok.get(name_or_token, name_or_token)
        return {"Cookie": f"Authorization={t}"}

    main = ws["main"]
    if subset:
        for who in ("owner", "stranger", "viewer"):
            add(f"flags:{who}", "GET", perm(main), auth(who))
        add("flags:no-token", "GET", perm(main))
        return cases

    # every person against the workspace they were seeded for, and against the others
    for who in people:
        for label, w in ws.items():
            add(f"person:{who}@{label}", "GET", perm(w), auth(who))
    # sessions with a second factor, an API key method or an SSO method on the policy workspaces
    for who in people:
        for suffix in ("_mfa", "_apikey", "_sso"):
            if who + suffix in tok:
                for label in ("totp", "sso", "both", "dis_both"):
                    if label in ws:
                        add(f"person:{who}{suffix}@{label}", "GET", perm(ws[label]), auth(who + suffix))
    # unknown / malformed workspace ids with a good token
    for label, w in (
        ("unknown-valid", "6a0000000000000000000000"),
        ("upper-case-main", main.upper()),
        ("mixed-case-main", main[:12].upper() + main[12:]),
        ("short", main[:23]),
        ("long", main + "0"),
        ("word", "nope"),
        ("non-hex-24", "g" * 24),
        ("encoded-space", "%20"),
        ("dot", "."),
        ("unicode", "%C3%A9"),
    ):
        add(f"id:{label}", "GET", perm(w), auth("owner"))
        add(f"id:{label}:no-token", "GET", perm(w))
    # token variants on the main workspace
    for name in (
        "owner_old_key", "owner_unknown_key", "owner_expired", "owner_refresh_typ", "owner_no_typ",
        "owner_no_sid", "owner_hs512", "owner_respondent_scope", "owner_extra_claims",
        "owner_bad_id_claim", "owner_numeric_id", "owner_nbf_future", "garbage",
        "owner_bad_plan", "owner_pro_plan", "owner_roles_string", "owner_roles_null", "owner_mfa_string",
        "owner_mfa_bad", "owner_email_verified_one", "owner_email_verified_two", "owner_iat_future",
        "owner_iat_past", "owner_iat_text", "owner_aud", "owner_iss", "owner_sid_number", "owner_sid_zero",
        "owner_scope_other_ws", "owner_scope_none", "owner_scope_bad_type", "owner_scope_unknown",
        "owner_auth_sso", "owner_float_exp", "owner_string_exp", "owner_nbf_past", "owner_extra_header",
    ):
        add(f"token:{name}@main", "GET", perm(main), auth(name))
        add(f"token:{name}@other", "GET", perm(ws["other"]), auth(name))
    t = tok["owner"]
    add("cookie:empty-value", "GET", perm(main), {"Cookie": "Authorization="})
    add("cookie:quoted", "GET", perm(main), {"Cookie": f'Authorization="{t}"'})
    add("cookie:lowercase-name", "GET", perm(main), {"Cookie": f"authorization={t}"})
    add("cookie:duplicate-later-wins", "GET", perm(main), {"Cookie": f"Authorization=bad; Authorization={t}"})
    add("cookie:duplicate-bad-later", "GET", perm(main), {"Cookie": f"Authorization={t}; Authorization=bad"})
    add("cookie:other-cookies", "GET", perm(main), {"Cookie": f"a=1; Authorization={t}; b=2"})
    add("cookie:no-spaces", "GET", perm(main), {"Cookie": f"a=1;Authorization={t};b=2"})
    add("cookie:header-not-cookie", "GET", perm(main), {"Authorization": t})
    add("cookie:bearer-header", "GET", perm(main), {"Authorization": f"Bearer {t}"})
    add("cookie:refresh-only", "GET", perm(main), {"Cookie": f"RefreshToken={t}"})
    add("cookie:refresh-token-in-access", "GET", perm(main), {"Cookie": f"Authorization={tok['owner_refresh_typ']}"})
    add("cookie:empty-refresh", "GET", perm(main), {"Cookie": f"Authorization={tok['owner_expired']}; RefreshToken="})
    # session refresh: the Python backend reads the session; bc-api delegates these
    add("refresh:expired+garbage-refresh", "GET", perm(main), {"Cookie": f"Authorization={tok['owner_expired']}; RefreshToken=garbage"})
    add("refresh:no-access+garbage-refresh", "GET", perm(main), {"Cookie": "RefreshToken=garbage"})
    # respondent scope
    add("scope:respondent@own", "GET", perm(main), auth("owner_respondent_scope"))
    add("scope:respondent@invalid-id", "GET", perm("nope"), auth("owner_respondent_scope"))
    # methods and paths
    for method in ("HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
        add(f"method:{method}", method, perm(main), auth("owner"))
        add(f"method:{method}:no-token", method, perm(main))
    add("path:trailing-slash", "GET", perm(main) + "/", auth("owner"))
    add("path:trailing-slash+query", "GET", perm(main) + "/?a=b", auth("owner"))
    add("path:trailing-slash:no-token", "GET", perm(main) + "/")
    add("path:query-string", "GET", perm(main) + "?x=1&y=2", auth("owner"))
    add("path:unknown-under-workspace", "GET", f"/api/v1/workspaces/{main}/permissionz", auth("owner"))
    add("path:deeper", "GET", perm(main) + "/extra", auth("owner"))
    add("path:double-slash", "GET", f"/api/v1/workspaces//{main}/permissions", auth("owner"))
    add("path:upper-case-segment", "GET", f"/api/v1/workspaces/{main}/Permissions", auth("owner"))
    add("path:no-prefix", "GET", f"/workspaces/{main}/permissions", auth("owner"))
    add("path:root", "GET", "/")
    # CORS (allowed origin comes from the allowed_origins table)
    for label, origin in (
        ("allowed", "https://app.example.test"),
        ("denied", "https://evil.example.test"),
        ("null", "null"),
        ("trailing-slash", "https://app.example.test/"),
        ("case", "https://APP.example.test"),
    ):
        add(f"cors:{label}:200", "GET", perm(main), {**auth("owner"), "Origin": origin})
        add(f"cors:{label}:401", "GET", perm(main), {"Origin": origin})
        add(f"cors:{label}:404", "GET", "/nope", {"Origin": origin})
        add(f"cors:{label}:405", "POST", perm(main), {**auth("owner"), "Origin": origin})
        add(f"cors:{label}:422", "GET", perm("nope"), {**auth("owner"), "Origin": origin})
        pre = {"Origin": origin, "Access-Control-Request-Method": "GET"}
        add(f"cors:{label}:preflight", "OPTIONS", perm(main), pre)
        add(f"cors:{label}:preflight-headers", "OPTIONS", perm(main), {**pre, "Access-Control-Request-Headers": "x-a, content-type"})
        add(f"cors:{label}:preflight-delete", "OPTIONS", perm(main), {**pre, "Access-Control-Request-Method": "DELETE"})
        add(f"cors:{label}:preflight-weird-method", "OPTIONS", perm(main), {**pre, "Access-Control-Request-Method": "FOO"})
        add(f"cors:{label}:preflight-unknown-path", "OPTIONS", "/nope", pre)
    add("cors:options-no-request-method", "OPTIONS", perm(main), {"Origin": "https://app.example.test"})
    add("cors:two-cookies+origin", "GET", perm(main), {**auth("viewer"), "Origin": "https://app.example.test"})
    return cases


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fixture = json.load(open(args[0]))
    py, rs = args[1], args[2]
    subset = "--subset" in sys.argv
    report = None
    if "--report" in sys.argv:
        report = sys.argv[sys.argv.index("--report") + 1]
    cases = build(fixture, subset)
    diffs, delegated, same = [], [], 0
    statuses = {}
    for name, method, path, headers in cases:
        a = call(py, method, path, headers)
        b = call(rs, method, path, headers)
        statuses[a[0]] = statuses.get(a[0], 0) + 1
        if b[0] == 501 and b"detail" in b[2] and a[0] != 501:
            delegated.append({"case": name, "python": a[0], "rust": "501 delegated"})
            continue
        if a == b:
            same += 1
            continue
        why = []
        if a[0] != b[0]:
            why.append(f"status {a[0]} != {b[0]}")
        if a[1] != b[1]:
            keys = sorted(set(a[1]) | set(b[1]))
            why.append("headers: " + "; ".join(f"{k}: {a[1].get(k)} != {b[1].get(k)}" for k in keys if a[1].get(k) != b[1].get(k)))
        if a[2] != b[2]:
            why.append(f"body: {a[2][:160]!r} != {b[2][:160]!r}")
        diffs.append({"case": name, "method": method, "path": path, "why": why})
    summary = {
        "cases": len(cases), "identical": same, "delegated": len(delegated), "differences": len(diffs),
        "python_status_histogram": dict(sorted(statuses.items())),
    }
    print(json.dumps(summary))
    for d in delegated:
        print("DELEGATED", d["case"], "(python", d["python"], ")")
    for d in diffs:
        print("DIFF", d["case"], d["method"], d["path"][:70])
        for w in d["why"]:
            print("    ", w)
    if report:
        json.dump({"summary": summary, "delegated": delegated, "differences": diffs}, open(report, "w"), indent=1)
    sys.exit(1 if diffs else 0)


main()
