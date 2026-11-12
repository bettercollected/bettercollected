# Automatic spam check (proof of work)

A response submit can ask the respondent's browser for a small calculation (a proof of
work) before it is accepted. There is nothing for the respondent to solve or see: no
puzzle, no image, no cookie, no request to a third party, and nothing about the
respondent is stored for it. It keeps out scripts that do not run JavaScript and makes
every request cost some CPU, so the per-client limits (`docs/sign-in-code-limits.md`)
cannot be evaded cheaply from many addresses. It does not stop an attacker who runs a
native solver: it is one layer next to the limits, not a replacement for them.

It is behind the server switch `CAPTCHA_ENABLED` (stored setting, off by default).

## Off means unchanged

With the switch off: the challenge route answers 404 `captcha_off`; the
`X-BC-Captcha` header is never read (no verification, no counter, no refusal for a
missing or garbage header); forms are served without the setting; creators cannot change
the per-form setting (422 `captcha_disabled` on the settings PATCH, the form spec API
and the operations the AI and MCP use; a value already stored is kept, neither enforced
nor shown); nothing is recorded.

## Protocol

1. The form page (when the form is served with `captchaRequired`) waits for the
   respondent's first interaction, then `POST /workspaces/{id}/captcha/challenge`
   with `{"purpose": "submit", "formId": ...}`. The answer is `{challenge, algorithm,
   bits, subpuzzles, expiresAt}`, never cached, no cookie.
2. A Web Worker (the static file `webapp/public/captcha/worker-v1.js`, built from `webapp/src/utils/captcha/captcha-worker.ts` by `yarn build:captcha-worker`; a test fails when the file is not what the build makes) finds 8 counters `c_i` such that `SHA-256(challenge ":" i ":" c_i)`
   starts with at least `bits - 3` zero bits (2^bits hashes expected in all; eight small
   puzzles keep the spread of the solve time small). Where no worker can start (an embed
   sandboxed without `allow-same-origin`) the same code runs on the main thread in slices
   of about 8 ms, within 25 seconds.
3. The submit carries `X-BC-Captcha: <challenge>.<c_0>,...,<c_7>`.
4. The server checks, cheapest first and touching the database last: length, HMAC,
   expiry (60 s of skew), purpose, workspace and form, the network tag, the difficulty
   floor, the eight hashes, and then the single-use claim of the nonce
   (`FixedWindowRateLimiter.claim`, which stores only a hash of the nonce).
   A refusal is 422 with `captcha_missing`, `captcha_invalid`, `captcha_expired` or
   `captcha_replayed`, and stored nothing; the page asks for a new challenge and sends
   once more. A network error or a 5xx is never retried.

The challenge is `base64url(claims) "." HMAC-SHA256`, signed under a key derived from the
JWT key ring with a purpose label of its own (a key rotation drops nothing). The network
tag is the first 8 bytes of an HMAC of the client key under a salt derived from the UTC
day, so it changes daily and needs no storage; it is empty when the client is not known
(a proxy that is not in `TRUSTED_PROXIES`), as for the per-client limits.

## Difficulty

`bits` is the base for the purpose (`API_CAPTCHA_BASE_BITS_SUBMIT`, 14 to 20, default 17)
plus pressure, at most +4, and never above 20; a signed-in respondent gets 3 less, never
below 14.

| Pressure (kept in this process's memory, never in the database) | Adds |
|---|---|
| challenges issued to the client in 10 minutes: 6 free, then one per doubling | up to +3 |
| 3 or more failed checks of the client in 10 minutes | +2 |
| the form's submits in the last minute (this process): over 30, over 120 | +1, +2 |
| the operator's `API_CAPTCHA_DIFFICULTY_BOOST` (0 to 4), for an attack in progress | up to +4 |

Why the ceiling is 20: the work doubles with every bit, so 20 bits is 8 times the base of 17. Measured with
the shipped solver under CPU throttling, 17 bits takes about 1.5 s (median) on a mid-range phone and about 2.5 s on
a low-end one; 20 bits is about 12 s and 20 s, inside the solver's 25 s budget. 21 bits would be about 23 s and 40 s,
past it.

The challenge route itself is limited to 60 a minute per client (429 `rate_limited` with
`Retry-After`). A client that is not known is neither counted nor limited there.

## Where it applies

The respondent route `POST /workspaces/{id}/forms/{id}/response` only, when the form
asks for it: on unless the creator turned it off (Settings, Respondent experience).
The Submissions API with a key never passes through that route and is exempt by
construction. The builder's preview sends nothing.

## Logs

Counts by outcome only (`captcha outcome=verified purpose=submit`); never a challenge, a
proof, a tag or an address.
