"""The vectors of every HMAC-derived value, identifier and hash: each expected
value is what the backend's own function returns for the inputs written beside
it. Keys are generated here for the run (throw-away); no application settings
are read (``pyload``)."""

import asyncio
import datetime as dt
import importlib
import json
import secrets
from pathlib import Path
from types import SimpleNamespace

import pyload

pyload.install()
pyload._stub_missing("re2")

from cryptography.fernet import Fernet  # noqa: E402
from common.settings import key_ring  # noqa: E402

T0 = 1_700_000_000  # seconds
WS = "6a0000000000000000000001"
FORM = "6a0000000000000000000002"
USER = "6a0000000000000000000003"


def mod(name):
    return importlib.import_module(name)


def set_jwt(ring: str) -> None:
    pyload.settings.auth_settings.JWT_SECRET = ring


def flip(text: str, index: int) -> str:
    chars = list(text)
    chars[index] = "A" if chars[index] != "A" else "B"
    return "".join(chars)


def ms(seconds: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(seconds, dt.timezone.utc)


# --------------------------------------------------------------- pieces ----


def signed_tokens(ring_a: str, ring_b: str) -> list:
    """The three claim-bearing tokens (cursor, AI notice, option share)."""
    cursor = mod("backend.app.services.response_cursor")
    notice = mod("backend.app.services.ai.notice_token")
    share = mod("backend.app.services.option_sources.share_token")
    listing = mod("backend.app.models.filter_queries.response_list")
    cases = []

    query = listing.ResponseListQuery(
        filters=listing.ResponseListFilters(
            submitted_from=ms(T0 - 86400),
            status=(listing.DeletionStatusFilter.PENDING,),
            form_version=(2, 1),
            search="grace@voorbeeld.example",
        ),
        size=50,
    )
    other_query = listing.ResponseListQuery(size=50)
    anchor = cursor.Anchor(page=3, version=None, created_at=ms(T0 - 3600), row_id="6a00000000000000000000ff")

    def add(purpose, name, ring, token, suffix, python_ok, claims):
        cases.append(
            {
                "purpose": purpose,
                "name": name,
                "ring": ring,
                "token": token,
                "suffix": suffix,
                "expect_claims": claims if python_ok else None,
            }
        )

    for label, ring_for_issue in (("current key", ring_a), ("previous key", ring_b)):
        set_jwt(ring_for_issue)
        c_token = cursor.issue(WS, FORM, query, anchor, now=ms(T0))
        n_token = notice.issue_token(
            workspace_id=WS, form_id=FORM, provider="openai", provider_name="OpenAI", enabled_at=ms(T0 - 5), now=ms(T0)
        )
        s_token = share.issue_token(workspace_id=WS, form_id=FORM, question_ids=["q-b", "q-a", "é"], now=ms(T0))
        set_jwt(f"{ring_a},{ring_b}")
        fingerprint = query.filters.fingerprint()
        for purpose, token, suffix in (("cursor", c_token, fingerprint), ("notice", n_token, None), ("share", s_token, None)):
            body = token.split(".")[1]
            claims = json.loads(cursor._unb64(body))
            add(purpose, f"{label}", f"{ring_a},{ring_b}", token, suffix, True, claims)
            add(purpose, f"{label}: ring of the other key only", ring_a if label == "previous key" else ring_b, token, suffix, False, None)
        # Python is the oracle for acceptance: a cursor read for this exact query
        set_jwt(f"{ring_a},{ring_b}")
        assert cursor.read(c_token, WS, FORM, query, now=ms(T0 + 5)).page == 3
        try:
            cursor.read(c_token, WS, FORM, other_query, now=ms(T0 + 5))
            raise AssertionError("a cursor for other filters must not read")
        except cursor.InvalidCursor:
            pass

    set_jwt(f"{ring_a},{ring_b}")
    c_token = cursor.issue(WS, FORM, query, anchor, now=ms(T0))
    n_token = notice.issue_token(workspace_id=WS, form_id=FORM, provider="openai", provider_name="OpenAI", enabled_at=ms(T0 - 5), now=ms(T0))
    s_token = share.issue_token(workspace_id=WS, form_id=FORM, question_ids=["q1"], now=ms(T0))
    for purpose, token, suffix, verifier in (
        ("cursor", c_token, query.filters.fingerprint(), lambda t, sfx: cursor._verifies(t.split(".")[2], f"{t.split('.')[0]}.{t.split('.')[1]}|{sfx}")),
        ("notice", n_token, None, lambda t, sfx: notice._verifies(t.split(".")[2], ".".join(t.split(".")[:2]))),
        ("share", s_token, None, lambda t, sfx: share._verifies(t.split(".")[2], ".".join(t.split(".")[:2]))),
    ):
        parts = token.split(".")
        damaged = {
            "signature flipped": ".".join([parts[0], parts[1], flip(parts[2], 3)]),
            "payload flipped": ".".join([parts[0], flip(parts[1], 5), parts[2]]),
            "version changed": ".".join(["x9", parts[1], parts[2]]),
            "no signature": ".".join(parts[:2]),
            "extra part": token + ".x",
            "signature truncated": ".".join([parts[0], parts[1], parts[2][:-4]]),
            "empty": "",
        }
        for name, bad in damaged.items():
            ok = False
            try:
                ok = len(bad.split(".")) == 3 and bad.split(".")[0] == parts[0] and verifier(bad, suffix)
            except Exception:
                ok = False
            assert not ok, (purpose, name)
            add(purpose, f"damaged: {name}", f"{ring_a},{ring_b}", bad, suffix, False, None)
        if purpose == "cursor":
            add(purpose, "fingerprint of other filters", f"{ring_a},{ring_b}", token, other_query.filters.fingerprint(), False, None)
    return cases


def captcha_vectors(ring_a: str, ring_b: str) -> dict:
    challenge = mod("backend.app.services.captcha.challenge")
    service = mod("backend.app.services.captcha.service")
    set_jwt(f"{ring_a},{ring_b}")
    now = ms(T0)
    issued = challenge.issue(
        purpose="submit", workspace_id=WS, form_id=FORM, bits=14, client="203.0.113.9", nonce=bytes(range(16)), now=now
    )
    discounted = challenge.issue(
        purpose="mail", workspace_id=WS, form_id=FORM, bits=14, client="", discounted=True, nonce=bytes(range(16, 32)), now=now
    )
    set_jwt(ring_b)
    older = challenge.issue(
        purpose="submit", workspace_id=WS, form_id=FORM, bits=14, client="203.0.113.9", nonce=bytes(range(32, 48)), now=now
    )
    set_jwt(f"{ring_a},{ring_b}")
    keys = challenge._keys()
    proofs = []
    for name, token, client, purpose in (
        ("signed with the current key", issued, "203.0.113.9", "submit"),
        ("signed with the previous key", older, "203.0.113.9", "submit"),
        ("a signed-in challenge without a client", discounted, "", "mail"),
    ):
        counters = challenge.solve(token)
        header = challenge.proof(token, counters)
        claims = challenge.check(header, purpose=purpose, workspace_id=WS, form_id=FORM, client=client, now=now)
        proofs.append(
            {
                "name": name,
                "header": header,
                "client": client,
                "day": claims.day,
                "tag": claims.tag,
                "bits": claims.bits,
                "nonce": claims.nonce,
                "spent_id": hashlib_sha256(claims.nonce.encode("ascii", "ignore")),
                "claims": challenge.unverified_claims(header),
            }
        )
    # the spent-nonce id drops non-ASCII characters
    spent = [{"nonce": n, "expect": hashlib_sha256(n.encode("ascii", "ignore"))} for n in ["abc", "abéc", "é", "", "A_-9"]]
    tags = []
    for day in (19675, 19676):
        for client in ("203.0.113.9", "2001:db8::1", "", "é"):
            tags.append({"day": day, "client": client, "expect": challenge.ip_tag(keys[0], day, client)})
    days = [{"unix": t, "expect": challenge.day_number(ms(t))} for t in (0, 86399, 86400, T0, T0 + 86399)]
    pow_cases = []
    for solved in (issued + "x", older):
        for bits in (14, 17):
            for index, counter in ((0, "0"), (1, "12345"), (7, "999999999999")):
                digest = challenge._hash(solved, index, counter)
                pow_cases.append(
                    {"solved": solved, "index": index, "counter": counter, "zero_bits": challenge.leading_zero_bits(digest)}
                )
    return {
        "proofs": proofs,
        "spent": spent,
        "tags": tags,
        "days": days,
        "pow": pow_cases,
        "keys_ring": f"{ring_a},{ring_b}",
        "issued": issued,
    }


def hashlib_sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def links(ring_a: str, ring_b: str, identity_key_text: str) -> dict:
    export = mod("backend.app.services.response_export.links")
    run = mod("backend.app.services.action_run_token")
    identity = mod("backend.app.utils.respondent_identity")
    out = {"export": [], "run": []}
    ids = ("6a00000000000000000000e1", WS, FORM, USER)
    for ring_for_issue, label in ((ring_a, "current"), (ring_b, "previous")):
        set_jwt(ring_for_issue)
        token = export.issue(*ids, now=float(T0))
        set_jwt(f"{ring_a},{ring_b}")
        for now, name in ((T0 + 10.5, "inside"), (T0 + 300, "at the limit"), (T0 + 301, "expired"), (T0 - 5, "before")):
            out["export"].append(
                {
                    "name": f"{label} key, {name}",
                    "ring": f"{ring_a},{ring_b}",
                    "token": token,
                    "ids": list(ids),
                    "now": now,
                    "expect": export.check(token, *ids, now=now),
                }
            )
    set_jwt(f"{ring_a},{ring_b}")
    good = export.issue(*ids, now=float(T0))
    for name, token, use_ids in (
        ("other user", good, (*ids[:3], "someone-else")),
        ("empty", "", ids),
        ("no dot", good.replace(".", ""), ids),
        ("no signature", good.split(".")[0] + ".", ids),
        ("letters in the expiry", "12ab." + good.split(".")[1], ids),
        ("tampered signature", good[:-1] + ("0" if good[-1] != "0" else "1"), ids),
        ("unicode digits in the expiry", "٣٣." + good.split(".")[1], ids),
        ("huge expiry", "9" * 40 + "." + good.split(".")[1], ids),
        ("another export", good, ("6a00000000000000000000e2", *ids[1:])),
    ):
        out["export"].append(
            {
                "name": name,
                "ring": f"{ring_a},{ring_b}",
                "token": token,
                "ids": list(use_ids),
                "now": T0 + 1.0,
                "expect": export.check(token, *use_ids, now=T0 + 1.0),
            }
        )
    # JSON text of ids with characters the default dumps escapes
    for odd_ids in (
        ("\u00e9\u00e9", 'q"uote', "back\\slash", "tab\tnl\n"),
        ("\u2603", "\U0001f600", "\x7f\x01", "x/y"),
    ):
        odd = export.issue(*odd_ids, now=float(T0))
        out["export"].append(
            {
                "name": "ids that dumps escapes",
                "ring": f"{ring_a},{ring_b}",
                "token": odd,
                "ids": list(odd_ids),
                "now": T0 + 1.0,
                "expect": export.check(odd, *odd_ids, now=T0 + 1.0),
            }
        )

    pyload.settings.respondent_identity.KEY = identity_key_text
    run_ids = (WS, FORM, "6a00000000000000000000a1", "6a00000000000000000000f1")
    token = run.run_token(*run_ids, now=float(T0))
    for now, name in ((T0 + 5.0, "inside"), (T0 + 86400.0, "at the limit"), (T0 + 86401.0, "expired")):
        out["run"].append({"name": name, "token": token, "ids": list(run_ids), "now": now, "expect": run.check_run_token(token, *run_ids, now=now)})
    for name, tok, use in (
        ("other response", token, (*run_ids[:3], "other")),
        ("empty", "", run_ids),
        ("tampered", token[:-1] + ("0" if token[-1] != "0" else "1"), run_ids),
    ):
        out["run"].append({"name": name, "token": tok, "ids": list(use), "now": T0 + 5.0, "expect": run.check_run_token(tok, *use, now=T0 + 5.0)})
    out["run_lock"] = {"ids": ["a", "f", "r"], "expect": run.run_lock("a", "f", "r")}
    out["identity_key"] = identity_key_text
    return out


def identity_vectors(key_text: str) -> dict:
    identity = mod("backend.app.utils.respondent_identity")
    key = identity.key_bytes(key_text)
    emails = ["grace@voorbeeld.example", "Grace@Voorbeeld.Example", "", "é@voorbeeld.example"]
    rows = []
    for email in emails:
        value = identity.identity_of(email, key)
        rows.append({"email": email, "md5": identity.hash_string(email), "identity": value})
    legacy = identity.hash_string("legacy@voorbeeld.example")
    pyload.settings.respondent_identity.KEY = key_text
    decode = []
    import base64
    import hashlib

    def random_looking(want_url_chars: bool) -> bytes:
        for i in range(1000):
            raw = hashlib.sha256(b"identity-vector-%d" % i).digest()
            text = base64.urlsafe_b64encode(raw).decode()
            if (("-" in text or "_" in text) == want_url_chars) and any(c.isdigit() for c in text) and any(c.islower() for c in text) and any(c.isupper() for c in text):
                return raw
        raise AssertionError

    raw = random_looking(False)
    raw_url = random_looking(True)
    weak = bytes(range(7, 39))
    for name, text in (
        ("hex", raw.hex()),
        ("hex upper", raw.hex().upper()),
        ("hex with spaces around", "  " + raw.hex() + "\n"),
        ("base64 standard", base64.b64encode(raw).decode()),
        ("base64 unpadded", base64.b64encode(raw).decode().rstrip("=")),
        ("base64 url-safe", base64.urlsafe_b64encode(raw_url).decode()),
        ("base64 url-safe unpadded", base64.urlsafe_b64encode(raw_url).decode().rstrip("=")),
        ("odd hex", raw.hex()[:-1]),
        ("short hex", raw.hex()[:62]),
        ("not base64", "!!!" * 20),
        ("empty", ""),
        ("weak: counting sequence hex", weak.hex()),
        ("weak: repeated block", (bytes(range(1, 17)) * 3).hex()),
    ):
        try:
            got = identity.key_bytes(text)
            decode.append({"name": name, "text": text, "expect": got.hex()})
        except identity.IdentityKeyError:
            decode.append({"name": name, "text": text, "expect": None})
    return {
        "key": key_text,
        "check_value": identity.key_check_value(key),
        "rows": rows,
        "legacy": {"md5": legacy, "converted": identity.convert_legacy(key, legacy), "v2_unchanged": identity.convert_legacy(key, rows[0]["identity"])},
        "decode": decode,
        "matches": [
            {"stored": rows[0]["identity"], "email": emails[0], "expect": identity.matches(rows[0]["identity"], emails[0], key)},
            {"stored": rows[0]["identity"], "email": emails[1], "expect": identity.matches(rows[0]["identity"], emails[1], key)},
            {"stored": legacy, "email": "legacy@voorbeeld.example", "expect": identity.matches(legacy, "legacy@voorbeeld.example", key)},
            {"stored": "", "email": "x", "expect": identity.matches("", "x", key)},
        ],
    }


def drafts(ring_a: str, ring_b: str) -> dict:
    tokens = mod("backend.app.services.form_drafts.tokens")
    out = {"hash": [], "address": [], "split": [], "ring": f"{ring_a},{ring_b}"}
    old = tokens.DraftKeys(ring_b)
    new = tokens.DraftKeys(f"{ring_a},{ring_b}")
    draft_id = "6a00000000000000000000aa"
    secret = tokens.new_secret()
    assert len(secret) == 43
    stored_new = new.hash_secret(tokens.TOKEN, draft_id, secret)
    stored_old = old.hash_secret(tokens.TOKEN, draft_id, secret)
    for name, stored in (("written by the current key", stored_new), ("written by the previous key", stored_old), ("none", None), ("other", "0" * 64)):
        for purpose in (tokens.TOKEN, tokens.EDIT_KEY):
            out["hash"].append(
                {
                    "name": f"{name}, checked as {purpose}",
                    "draft_id": draft_id,
                    "secret": secret,
                    "purpose": purpose,
                    "stored": stored,
                    "expect_matches": new.matches(purpose, draft_id, secret, stored),
                }
            )
    out["hash_values"] = [
        {"purpose": p, "draft_id": draft_id, "secret": secret, "expect": new.hash_secret(p, draft_id, secret)}
        for p in (tokens.TOKEN, tokens.EDIT_KEY)
    ]
    out["single_secret"] = {"secret": "x" * 10, "expect": tokens.DraftKeys("x" * 10).hash_secret(tokens.TOKEN, draft_id, "s")}
    out["empty_secret"] = {"expect": tokens.DraftKeys("").hash_secret(tokens.TOKEN, draft_id, "s")}
    for address in ("Grace@Voorbeeld.Example", "  grace@voorbeeld.example\n", "no-at-sign", "a@b@C.example", "UPPER@EXAMPLE.ORG", "x\x1f@y.example", "é@voorbeeld.example", "grace@bücher.example", "ＡＢＣ@x.example"):
        normalised = tokens.normalised_address(address)
        out["address"].append(
            {
                "address": address,
                "normalised": normalised,
                "ascii": address.isascii(),
                "key": new.address_key(FORM, address),
                "keys": new.address_keys(FORM, address),
            }
        )
    for value in (
        f"{draft_id}.{secret}",
        f"{draft_id}.{secret}x",
        f"{draft_id.upper()}.{secret}",
        f"{draft_id}.{secret[:-1]}",
        f"{draft_id}.{'é' * 43}",
        "x" * 81,
        "",
        f"{draft_id}-{secret}",
        f"{draft_id}.{'A' * 43}",
    ):
        parts = tokens.split(value)
        out["split"].append({"value": value, "expect": list(parts) if parts else None})
    return out


def counters(ring_a: str, ring_b: str) -> dict:
    limiter = mod("backend.app.services.rate_limiter")
    ids = mod("backend.app.services.option_sources.ids")
    out = {"rate": [], "option": []}
    for ring in (ring_a, f"{ring_a},{ring_b}", "short-secret"):
        lim = limiter.FixedWindowRateLimiter(None, ring)
        for scope, client, window in (("public-api", "203.0.113.9", 56666666), ("submit", "", 0), ("mcp", "é\n", 12), ("s", "c", 2**40)):
            out["rate"].append({"ring": ring, "scope": scope, "client": client, "window": window, "expect": lim.counter_id(scope, client, window)})
    set_jwt(f"{ring_a},{ring_b}")
    for label in ("Ja", "ja", "É", "", "a\0b"):
        out["option"].append(
            {
                "ring": f"{ring_a},{ring_b}",
                "workspace": WS,
                "form": FORM,
                "question": "q-1",
                "label": label,
                "expect": ids.answer_option_ids(WS, FORM, "q-1", label),
            }
        )
    out["shape"] = [{"value": v, "expect": ids.is_source_id(v)} for v in ("li" + "a" * 22, "fa" + "0" * 22, "xx" + "0" * 22, "li" + "A" * 22, "li" + "a" * 21, "fa" + "0" * 23, 5, None)]
    out["shape"] = [s for s in out["shape"] if isinstance(s["value"], str)]
    return out


def signatures() -> dict:
    payload = mod("backend.app.services.webhooks.payload")
    scim = mod("backend.app.services.scim.signature")
    body = b'{"event":"submission","data":{"name":"Ada \xc3\xa9"}}'
    secret = secrets.token_urlsafe(32)
    web = []
    for ts in (0, 1700000000, 99999999999):
        web.append({"secret": secret, "timestamp": ts, "body_b64": b64(body), "expect": payload.sign(secret, ts, body)})
    web.append({"secret": "é-secret", "timestamp": 5, "body_b64": b64(b""), "expect": payload.sign("é-secret", 5, b"")})
    ts_ms = T0 * 1000
    header = scim.sign(secret, body, ts_ms)
    cases = []

    def add(name, hdr, now, sec=secret, tol=300):
        try:
            result = scim.verify(hdr, body, sec, tol, now=now)
            expect = {"ok": result}
        except scim.BadSignature as bad:
            expect = {"error": bad.code}
        cases.append({"name": name, "header": hdr, "secret": sec, "tolerance": tol, "now": now, "body_b64": b64(body), "expect": expect})

    add("valid", header, T0 + 1.0)
    add("expired", header, T0 + 301.0)
    add("future", header, T0 - 301.0)
    add("at the edge", header, T0 + 300.0)
    add("none", None, T0)
    add("empty", "", T0)
    add("wrong secret", header, T0, sec="other")
    add("no secret", header, T0, sec="")
    add("uppercase hex", header.replace(header.split("s=")[1], header.split("s=")[1].upper()), T0)
    add("short signature", f"t={ts_ms},s=abc", T0)
    add("no timestamp", f"s={header.split('s=')[1]}", T0)
    add("junk timestamp", f"t=abc,s={header.split('s=')[1]}", T0)
    add("repeated keys keep the first", f"t={ts_ms},s={header.split('s=')[1]},t=1,s=zz", T0)
    add("extra keys", f"v1=zzz,t={ts_ms},s={header.split('s=')[1]}", T0)
    add("spaces around items", f" t={ts_ms} , s={header.split('s=')[1]} ", T0)
    add("too long", "t=1," + "x" * 600, T0)
    add("non-ascii signature", f"t={ts_ms},s=" + "é" * 64, T0)
    return {"webhook": web, "scim": cases}


def b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode()


def oauth_and_keys(fernet_a: str, fernet_b: str) -> dict:
    sheets = mod("backend.app.services.google_sheets_oauth")
    state = mod("backend.app.services.integration_oauth_state")
    sso = mod("backend.app.services.sso.login_service")
    keys = mod("backend.app.services.ai.api_keys")
    out = {"pkce": [], "nonce": [], "sso": [], "api": []}
    for member in (fernet_a, fernet_b):
        for st in ("gAAAAAB-state", "é", "", "a" * 400):
            verifier = sheets.pkce_code_verifier(st, member)
            out["pkce"].append({"member": member, "state": st, "verifier": verifier, "challenge": sheets.pkce_code_challenge(verifier)})
    pyload.settings.auth_settings.AES_HEX_KEY = f"{fernet_a},{fernet_b}"
    out["pkce_default"] = {"ring": f"{fernet_a},{fernet_b}", "state": "s1", "verifier": sheets.pkce_code_verifier("s1")}
    for nonce in ("n-1", "é", ""):
        out["nonce"].append({"nonce": nonce, "expect": state.state_nonce_hash(nonce)})
        out["sso"].append({"nonce": nonce, "expect": sso.nonce_hash(nonce), "none_hash": sso.nonce_hash(None)})
    token = "bc_" + secrets.token_hex(32)
    out["api"] = [{"token": token, "hash": keys._hash(token), "prefix": token[: len(keys.TOKEN_PREFIX) + 8]}, {"token": "bc_é", "hash": keys._hash("bc_é"), "prefix": "bc_é"[:11]}]
    out["state_max_age"] = sheets.STATE_MAX_AGE_SECONDS
    return out


def totp_vectors() -> dict:
    totp = mod("common.security.totp")
    recovery = mod("common.security.recovery")
    sealing = mod("backend.app.services.mfa.sealing")

    class Clock:
        def __init__(self, t):
            self.t = t

        def time(self):
            return self.t

    out = {"hotp": [], "verify": [], "decode": [], "recovery": []}
    rfc = b"12345678901234567890"  # RFC 4226 appendix D
    for counter in (0, 1, 2, 9, 1234567890, 2**40):
        out["hotp"].append({"key_hex": rfc.hex(), "counter": counter, "expect": totp.hotp(rfc, counter)})
    secret = totp.generate_secret()
    out["secret"] = secret
    for now in (59.0, 1111111109.0, float(T0), float(T0) + 29.9, 0.0, 15.0):
        for delta in (-60, -30, 0, 30, 60):
            if now + delta < 0:
                continue
            code = totp.code_at(secret, now + delta)
            matched = totp.verify(secret, code, Clock(now))
            out["verify"].append({"secret": secret, "code": code, "now": now, "expect": matched})
    now = float(T0)
    good = totp.code_at(secret, now)
    for name, code in (("spaces", " " + good[:3] + " " + good[3:] + " "), ("too short", good[:5]), ("letters", "abcdef"), ("unicode digits", "١٢٣٤٥٦"), ("empty", "")):
        out["verify"].append({"secret": secret, "code": code, "now": now, "expect": totp.verify(secret, code, Clock(now)), "name": name})
    for text in (secret, secret.lower(), " ".join([secret[:8], secret[8:]]), secret + "====", "", "!!!", "A", "AAA", "AAAAAA", "MFRGG===", "mfrgg", "MFRGGZDF", "MFRGGZDFMY"):
        try:
            out["decode"].append({"text": text, "expect": totp.decode_secret(text).hex()})
        except ValueError:
            out["decode"].append({"text": text, "expect": None})
    for last, matched in ((None, 5), (4, 5), (5, 5), (6, 5), (None, 0)):
        out.setdefault("replay", []).append({"last": last, "matched": matched, "expect": totp.next_last_used_step(last, matched)})
    for code in ("ABCD-EFGH-IJKL-MNOP", "abcd efgh ijkl mnop", "ABCDEFGHIJKLMNOP", "ABCD-EFGH-IJKL-MNO1", "short", "", "ab\tcd\nef-gh-ijklmnop"):
        out["recovery"].append(
            {
                "code": code,
                "normalised": recovery.normalise(code),
                "well_formed": recovery.is_well_formed(code),
                "hash": sealing.hash_recovery_code(USER, code),
            }
        )
    sample = recovery.generate_code()
    out["recovery_sample_shape"] = {"code": sample, "well_formed": recovery.is_well_formed(sample)}
    return out


def ids_vectors(ring_a: str) -> dict:
    analytics = mod("backend.app.repositories.postgres.analytics")
    exports = mod("backend.app.repositories.postgres.response_exports")
    imports = mod("backend.app.repositories.postgres.response_imports")
    responses = mod("backend.app.repositories.postgres.responses")
    idem = mod("backend.app.services.idempotency")
    migrate = mod("backend.app.services.builtin_actions.migrate")
    domains = mod("backend.app.services.custom_domain_service")
    import hashlib as _hashlib
    import typing as _typing

    spec = pyload.extract(
        "app/services/form_spec/writes.py",
        ("_EPOCH", "_ms", "form_etag"),
        json=json, hashlib=_hashlib, dt=dt, Optional=_typing.Optional, Dict=_typing.Dict, Any=_typing.Any,
    )
    promotion = pyload.extract(
        "app/services/form_promotion/service.py",
        ("spec_hash",),
        json=json, hashlib=_hashlib, Dict=_typing.Dict, Any=_typing.Any,
    )
    policy = mod("backend.app.services.reporting.policy")
    scim_hook = mod("backend.app.services.scim.webhook_service")
    exporter = mod("backend.app.services.open_formulieren.exporter")

    out = {}
    out["captcha_count"] = [
        {"key": list(k), "expect": analytics.captcha_count_id(tuple(k))}
        for k in (("2026-11-16", WS, FORM, "submit", "refused"), ("d", "w", "f", "mail", "é"))
    ]
    out["lock"] = []
    for parts in (("tag", "Title"), ("responder", "grace@voorbeeld.example"), ("é", "x", "y"), ("single",), ()):
        captured = []

        class FakeSession:
            async def execute(self, statement):
                captured.append(list(statement.compile().params.values())[0])

        asyncio.run(responses._advisory_lock(FakeSession(), *parts))
        out["lock"].append({"parts": list(parts), "expect": captured[0]})
    out["workspace_lock"] = [
        {"kind": "export", "workspace": w, "expect": exports._workspace_lock_key(w)} for w in (WS, "x", "é")
    ] + [{"kind": "import", "workspace": w, "expect": imports._workspace_lock_key(w)} for w in (WS, "x", "é")]
    bodies = [b'{"b":1,"a":[1,2,{"z":null,"y":"\xc3\xa9"}],"f":1.0,"g":1e2}', b'{"a":1}', b"[]", b"not json", b"", b'{"a":1,"a":2}', b'"s"', b"12", b'{"\xc3\xa9":"\xf0\x9f\x98\x80"}', b'{"x": 1.5e-7, "y": 12345678901234567890}']
    out["request_hash"] = []
    for body in bodies:
        for method, path, extra in (("post", "/api/v1/forms", ()), ("PUT", "/x", ("k1", "é"))):
            out["request_hash"].append({"method": method, "path": path, "body_b64": b64(body), "extra": list(extra), "expect": idem.request_hash(method, path, body, *extra)})
    out["record_id"] = [{"key_id": "k", "key": "idem-1", "expect": idem._record_id("k", "idem-1")}]
    out["builtin_target"] = [{"args": ["webhook", "f", "a"], "expect": str(migrate.target_id("webhook", "f", "a"))}]
    out["custom_domain_key"] = [{"args": [WS, "forms.voorbeeld.example", "attempt-1"], "expect": domains.idempotency_key(WS, "forms.voorbeeld.example", "attempt-1")}]
    docs = [{"b": 1, "a": [1, 2.5, "é", None, True], "c": {"y": 1, "x": 2}}, {}, {"é": 1, "z": "\U0001f600", "\u0000": 1}, {"n": 1.0, "m": -0.0, "big": 2**53, "small": 1e-7}]
    out["spec_hash"] = [{"doc": d, "expect": promotion.spec_hash(d)} for d in docs]
    out["etag"] = [{"updated_ms": ms_, "doc": d, "expect": spec.form_etag(dt.datetime.fromtimestamp(ms_ / 1000, dt.timezone.utc), d)} for ms_, d in ((1700000000123, docs[0]), (0, docs[1]), (1700000000000, docs[2]))]
    out["policy_fingerprint"] = [{"visible": v, "expect": next(c for c in vars(policy).values() if isinstance(c, type) and "fingerprint" in vars(c)).fingerprint(v)} for v in (["q:b", "q:a"], [], ["é"])]
    out["scim_event"] = [
        {"directory": WS, "event": {"event": "user.created", "data": {"b": 1, "a": {"z": [1, 2]}}}, "timestamp_ms": T0 * 1000, "index": i, "expect": scim_hook.event_key(WS, {"event": "user.created", "data": {"b": 1, "a": {"z": [1, 2]}}}, T0 * 1000, i)}
        for i in (0, 3)
    ]
    cls = next(v for v in vars(exporter).values() if isinstance(v, type) and "_component_id" in vars(v))
    out["of_component"] = [
        {"seed": seed, "key": key, "expect": cls._component_id(SimpleNamespace(seed=seed), key)}
        for seed, key in (("s", "textfield"), ("seed-é", "a/b"))
    ]
    return out


def pyjson_vectors() -> list:
    texts = [
        '{"b":1,"a":2}', '[1,2.0,3.5,-0.0,0.1,1e16,1e-5,123456789.123456789,1.5e-7,100.0,1e22,12345678901234567890,9223372036854775807,-9223372036854775808,0.0001,0.00001,1e15,1e16]',
        '"plain"', '"\\u00e9\\u2603\\ud83d\\ude00\\n\\t\\r\\b\\f\\u0001\\u007f\\"\\\\/"', '{"\\u00e9":1,"z":2,"A":3,"\\ud83d\\ude00":4,"\\u00ff":5}',
        'null', 'true', 'false', '[]', '{}', '[[],{},[{}]]', '{"a":{"b":{"c":[1,{"d":null}]}}}',
    ]
    out = []
    for text in texts:
        value = json.loads(text)
        out.append(
            {
                "text": text,
                # object keys come out sorted here (a serde_json map is ordered),
                # so only the sorted forms are comparable; list-only values
                # (the export-link messages) have no keys to order
                "default": json.dumps(value, sort_keys=True),
                "compact": json.dumps(value, sort_keys=True, separators=(",", ":")),
                "canonical": json.dumps(value, sort_keys=True, separators=(",", ":")),
            }
        )
    return out


def b64_vectors() -> list:
    import base64

    cases = []
    samples = [b"", b"a", b"ab", b"abc", b"abcd", bytes(range(256)), b"\xfb\xff\xfe"]
    for data in samples:
        std = base64.b64encode(data).decode()
        url = base64.urlsafe_b64encode(data).decode()
        for name, text in (
            ("standard", std),
            ("url-safe", url),
            ("unpadded", url.rstrip("=")),
            ("newline", url + "\n"),
            ("space inside", url[:2] + " " + url[2:]),
            ("crlf", url[:4] + "\r\n" + url[4:]),
            ("junk char", url[:2] + "!" + url[2:]),
            ("data after padding", url + "AAAA") if url.endswith("=") else ("(none)", url),
        ):
            try:
                got = base64.urlsafe_b64decode(text).hex()
            except Exception:
                got = None
            cases.append({"name": name, "text": text, "python": got})
    return cases


# --------------------------------------------------------------- driver ----


def run(command: str, args: list) -> None:
    if command == "check-derived":
        check_derived(*args)
        return
    ring_a, ring_b = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    fernet_a, fernet_b = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    identity_key = secrets.token_hex(32)
    pyload.settings.respondent_identity.KEY = identity_key
    out = {
        "jwt": {"a": ring_a, "b": ring_b},
        "fernet": {"a": fernet_a, "b": fernet_b},
        "identity_key": identity_key,
        "t0": T0,
    }
    listing = mod("backend.app.models.filter_queries.response_list")
    out["check_fingerprint"] = listing.ResponseListQuery(
        filters=listing.ResponseListFilters(search="grace@voorbeeld.example"), size=50
    ).filters.fingerprint()
    out["signed"] = signed_tokens(ring_a, ring_b)
    out["captcha"] = captcha_vectors(ring_a, ring_b)
    out["links"] = links(ring_a, ring_b, identity_key)
    out["identity"] = identity_vectors(identity_key)
    out["drafts"] = drafts(ring_a, ring_b)
    out["counters"] = counters(ring_a, ring_b)
    out["signatures"] = signatures()
    out["oauth"] = oauth_and_keys(fernet_a, fernet_b)
    out["totp"] = totp_vectors()
    out["ids"] = ids_vectors(ring_a)
    out["pyjson"] = pyjson_vectors()
    out["b64"] = b64_vectors()
    Path(args[0]).parent.mkdir(parents=True, exist_ok=True)
    Path(args[0]).write_text(json.dumps(out, indent=1, ensure_ascii=True))
    print("wrote", args[0])


def check_derived(vector_path: str, rust_base: str) -> None:
    """Python verifies what Rust derived: every value must equal Python's own."""
    vector = json.loads(Path(vector_path).read_text())
    rust = json.loads(Path(rust_base + ".derived.json").read_text())
    ring_a, ring_b = vector["jwt"]["a"], vector["jwt"]["b"]
    ring = f"{ring_a},{ring_b}"
    checked = 0

    cursor = mod("backend.app.services.response_cursor")
    notice = mod("backend.app.services.ai.notice_token")
    share = mod("backend.app.services.option_sources.share_token")
    listing = mod("backend.app.models.filter_queries.response_list")
    set_jwt(ring)
    query = listing.ResponseListQuery(filters=listing.ResponseListFilters(search="grace@voorbeeld.example"), size=50)
    token = rust["cursor"]
    anchor = cursor.read(token, WS, FORM, query, now=ms(rust["issued"]))
    assert anchor.page == 4 and anchor.row_id == "6a00000000000000000000ee", "cursor"
    checked += 1
    assert share.shown_question_ids(rust["share"], workspace_id=WS, form_id=FORM, now=ms(rust["issued"])) == ["q-x", "q-y"], "share"
    checked += 1
    claims = json.loads(notice._unb64(rust["notice"].split(".")[1]))
    assert notice._verifies(rust["notice"].split(".")[2], ".".join(rust["notice"].split(".")[:2])), "notice signature"
    assert claims["p"] == "openai"
    checked += 1

    challenge = mod("backend.app.services.captcha.challenge")
    header = rust["captcha_proof"]
    claims = challenge.check(header, purpose="submit", workspace_id=WS, form_id=FORM, client="203.0.113.9", now=ms(rust["issued"]))
    assert claims.bits == 14
    checked += 1

    export = mod("backend.app.services.response_export.links")
    ids = tuple(rust["export_ids"])
    assert export.check(rust["export"], *ids, now=float(rust["issued"])) == "valid"
    checked += 1
    pyload.settings.respondent_identity.KEY = vector["identity_key"]
    run = mod("backend.app.services.action_run_token")
    assert run.check_run_token(rust["run"], *rust["run_ids"], now=float(rust["issued"])) == "valid"
    checked += 1
    identity = mod("backend.app.utils.respondent_identity")
    key = identity.key_bytes(vector["identity_key"])
    assert identity.identity_of("rust@voorbeeld.example", key) == rust["identity"]
    checked += 1

    tokens = mod("backend.app.services.form_drafts.tokens")
    keys = tokens.DraftKeys(ring)
    assert keys.matches(tokens.TOKEN, rust["draft"]["id"], rust["draft"]["secret"], rust["draft"]["hash"])
    assert keys.address_key(FORM, "rust@voorbeeld.example") == rust["draft"]["address"]
    checked += 2

    payload = mod("backend.app.services.webhooks.payload")
    scim = mod("backend.app.services.scim.signature")
    assert payload.verify(rust["secret"], 1700000000, b'{"a":1}', rust["webhook"])
    assert scim.verify(rust["scim"], b'{"a":1}', rust["secret"], 300, now=T0 + 1.0) == T0 * 1000
    checked += 2

    totp = mod("common.security.totp")

    class Clock:
        def time(self):
            return float(T0)

    assert totp.verify(rust["totp_secret"], rust["totp_code"], Clock()) is not None
    sealing = mod("backend.app.services.mfa.sealing")
    assert sealing.hash_recovery_code(USER, rust["recovery"]["code"]) == rust["recovery"]["hash"]
    recovery = mod("common.security.recovery")
    assert recovery.is_well_formed(rust["recovery"]["code"]) and recovery.is_well_formed(rust["recovery_generated"])
    checked += 3

    keys_mod = mod("backend.app.services.ai.api_keys")
    assert keys_mod._hash(rust["api"]["token"]) == rust["api"]["hash"] and rust["api"]["token"].startswith("bc_") and len(rust["api"]["token"]) == 67
    checked += 1
    sheets = mod("backend.app.services.google_sheets_oauth")
    assert sheets.pkce_code_verifier("state-1", vector["fernet"]["a"]) == rust["pkce"]["verifier"]
    assert sheets.pkce_code_challenge(rust["pkce"]["verifier"]) == rust["pkce"]["challenge"]
    checked += 2

    limiter = mod("backend.app.services.rate_limiter")
    assert limiter.FixedWindowRateLimiter(None, ring).counter_id("s", "c", 7) == rust["rate"]
    checked += 1
    idm = mod("backend.app.services.option_sources.ids")
    set_jwt(ring)
    assert idm.answer_option_ids(WS, FORM, "q", "ja") == rust["option"]
    assert idm.is_source_id(rust["new_item_id"])
    checked += 2
    import hashlib as _hashlib
    import typing as _typing

    spec = pyload.extract(
        "app/services/form_spec/writes.py",
        ("_EPOCH", "_ms", "form_etag"),
        json=json, hashlib=_hashlib, dt=dt, Optional=_typing.Optional, Dict=_typing.Dict, Any=_typing.Any,
    )
    doc = {"b": [1, 2.5, "é"], "a": None}
    assert spec.form_etag(ms(1700000000), doc) == rust["etag"]
    checked += 1
    print(f"python verified {checked} rust-derived values: ok")
