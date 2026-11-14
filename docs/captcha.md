# Automatic spam check (proof of work)

A response submit, and the mails the public can trigger (the sign-in code of a
respondent and of a creator, the link of a saved draft), can ask the browser for a small
calculation (a proof of work) before they are accepted. There is nothing for the respondent to solve or see: no
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
nor shown, and a write that leaves it as it is passes on every path); copying a form
to another workspace carries the stored value as it is; nothing is recorded.
The mail routes (sign-in codes, draft link) behave exactly as before: the header is not
read, nothing is claimed or counted, and a request without it is not refused. The
workspace default and the counts answer 404 `captcha_off` (a change of the default 422
`captcha_disabled`); a stored default is kept, neither served nor enforced; no count is
written.

## Protocol

1. The form page (when the form is served with `captchaRequired`) waits for the
   respondent's first interaction, then `POST /workspaces/{id}/captcha/challenge`
   with `{"purpose": "submit", "formId": ...}`. The answer is `{challenge, algorithm,
   bits, subpuzzles, expiresAt}`, never cached, no cookie. The form is looked up the
   way the submit looks it up: a private form the respondent may answer (a responder
   group admits them) gets a challenge like any other; one they may not answers 404
   like a form that does not exist.
2. A Web Worker (the static file `webapp/public/captcha/worker-v1.js`, built from `webapp/src/utils/captcha/captcha-worker.ts` by `yarn build:captcha-worker`; a test fails when the file is not what the build makes) finds 8 counters `c_i` such that `SHA-256(challenge ":" i ":" c_i)`
   starts with at least `bits - 3` zero bits (2^bits hashes expected in all; eight small
   puzzles keep the spread of the solve time small). Where no worker can start (an embed
   sandboxed without `allow-same-origin`) the same code runs on the main thread in slices
   of about 8 ms, within 25 seconds.
3. The submit carries `X-BC-Captcha: <challenge>.<c_0>,...,<c_7>`.
4. The server checks, cheapest first and touching the database last: length, HMAC,
   expiry (60 s of skew), purpose, workspace and form, the network tag, the difficulty
   floor, the eight hashes, and then the single-use claim of the nonce
   (`FixedWindowRateLimiter.claim`, which stores only a hash of the nonce, until
   5 minutes past the moment the proof stops being accepted, so that a replica whose
   clock runs behind cannot accept a proof the others already spent).
   A proof issued at the signed-in difficulty carries a signed flag `s`; the submit
   refuses it (`captcha_invalid`, before the nonce is claimed) unless the respondent is
   signed in on the submit as well.
   A refusal is 422 with `captcha_missing`, `captcha_invalid`, `captcha_expired` or
   `captcha_replayed`, and stored nothing; the page asks for a new challenge and sends
   once more. A network error or a 5xx is never retried.

The challenge is `base64url(claims) "." HMAC-SHA256`, signed under a key derived from the
JWT key ring with a purpose label of its own (a key rotation drops nothing). The network
tag is the first 8 bytes of an HMAC of the client key under a salt derived from the UTC
day, so it changes daily and needs no storage; it is empty when the client is not known
(a proxy that is not in `TRUSTED_PROXIES`), as for the per-client limits.

## Purposes: submit and mail

The challenge carries its purpose, and a proof is good only for the purpose, workspace
and form it was issued for: a proof for a submit is refused on a mail route and the other
way round (`captcha_invalid`, before anything is claimed).

| Purpose | Route | Bound to |
|---|---|---|
| `submit` | `POST /workspaces/{id}/forms/{id}/response` | workspace and form |
| `mail` | `POST /workspaces/{id}/auth/otp/send` (a respondent's sign-in code) | workspace, no form |
| `mail` | `POST /auth/creator/otp/send` (a creator's sign-in code) | no workspace, no form |
| `mail` | `POST /workspaces/{id}/forms/{id}/drafts/link` (the link of a saved draft) | workspace and form |

A mail challenge is `POST /workspaces/{id}/captcha/challenge` with `{"purpose": "mail"}`
(and `"formId"` for the draft link), or `POST /auth/captcha/challenge` for the creator.
The check on these routes has no creator opt-out: a mail sent costs the instance its
reputation, not just one form's. It comes first, before the per-address and per-client
limits of `docs/sign-in-code-limits.md` count, so a request without a proof is refused
(422 with the codes above) and uses up nobody's budget: someone who knows an address cannot
lock its owner out of the code mail without solving a proof for every request.

The pages do not know whether the server asks. They send the request as before; a
refusal for the spam check (`captcha_missing`) makes them solve a proof and send once
more, and later requests of that page solve first. A server with the switch off is
therefore never asked for a challenge and no worker is started. The draft link also
needs `SAVE_DRAFTS_ENABLED` and an anonymous respondent, as before; saving, opening and
discarding a draft need no proof.

## Difficulty

`bits` is the base for the purpose (`API_CAPTCHA_BASE_BITS_SUBMIT`, 14 to 20, default 17,
and `API_CAPTCHA_BASE_BITS_MAIL`, 14 to 20, default 18) plus pressure, at most +4, and never
above 20; a signed-in respondent gets 3 less on a submit, never below 14 (the challenge says
so, and the proof is good only for a signed-in submit). A mail has no discount (a sign-in
code is asked for by someone who is not signed in) and the form's submit rate is not part of
its pressure.

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

The page solves one challenge for one submit: nothing is solved ahead after a submit
and nothing on a timer, so an idle tab does no work. If the check was switched on while the
form was open, the first send goes without a proof, is refused (`captcha_missing`), and the
retry takes one whatever the page loaded with. A challenge request that takes more than
10 seconds is cut off and counts as a spam check that could not be completed.

While the switch is on a failed form lookup on the submit is an error (the repository's
own, 500), never a pass.

## Where it applies

The respondent route `POST /workspaces/{id}/forms/{id}/response`, when the form asks for it,
and the three mail routes above, always. Whether a form asks is, in this order: its own
setting (Settings, Respondent experience), else the workspace's default (Workspace, Spam
protection; `captcha_default`), else on. The Submissions API with a key never passes through
the submit route and is exempt by construction. The builder's preview sends nothing.

## Workspace default

`GET|PUT /workspaces/{id}/captcha/settings` (`workspace.manage`) reads and sets
`captcha_default`; the form page's `captchaRequired` and the submit's check follow the same
rule. A change is written to the workspace's activity log first (`captcha_setting_changed`:
who and the new value, no form), or refused (503 `audit_unavailable`). A form's own setting
changed from the form's settings is recorded the same way, with the form. (Changes made
through the form spec API and the operations the AI and MCP use are not recorded yet.)

## Counts

Outcomes are counted by UTC day, workspace (none for the creator's sign-in code), form (none
for a workspace's sign-in code), purpose and outcome (`issued`, `verified`, `missing`,
`invalid`, `expired`, `replayed`, `rate_limited`) in `captcha_daily_counts` (migration 0041).
Counts only: no address, no network, no challenge, no person.

The counting is a dictionary in the process's memory, never a write per request: the counts
are added to the table in one transaction every 60 seconds or when 500 different keys are
waiting, and when a page asks for them, so a flood of refused requests costs a dictionary
entry, not a database write. A restart or a database that cannot be reached loses what has
not been written (statistics, not a ledger; at most 5,000 keys wait). Rows older than
`API_FLOW_EVENTS_RETENTION_DAYS` (395 by default; 0 keeps them) are deleted, at most once a
day per process.

`GET /workspaces/{id}/forms/{id}/captcha/stats` (`analytics.read` on that form) and
`GET /workspaces/{id}/captcha/stats` (`workspace.manage`) answer the last 30 days as
`{days, submit: {passed, blocked}, mail: {passed, blocked}}`: `passed` is verified,
`blocked` is missing, invalid, expired or replayed. They are shown in the form's settings
and on the Spam protection page. Totals for the whole platform on the admin portal's
metrics page are not part of this change (they need a change to the portal's read-only
function in `postgres/ensure-admin-roles.sh`).

## Logs

Counts by outcome only (`captcha outcome=verified purpose=submit`); never a challenge, a
proof, a tag or an address.
