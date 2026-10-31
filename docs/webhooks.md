# Webhooks

A form's owners and admins can send the answers of chosen questions to an https address of their own, as soon as a response is submitted. Off by default
(`WEBHOOKS_ENABLED`). Webhooks contain no creator code: they run in the backend's jobs worker, on their own queue, never in the actions executor.

## Switch

`WEBHOOKS_ENABLED` (`true` / `false`, default `false`; [settings inventory](settings-inventory.md)). While it is off:

- creating a webhook, switching one on and sending a test event answer **422** `webhooks_off`;
- no submission queues a delivery, the jobs send nothing (a delivery waiting for a retry is parked and queued again when the switch is turned on), and the
  respondent's privacy panel names no destination;
- everything else still answers: the list and detail reads, edits that do not switch one on, switching one off, deleting, rotating a secret, the delivery log and the change history. Saved webhooks and the log stay as they are.

## What a webhook is

One webhook belongs to one form (at most 5 per form). It has:

| Part | Rule |
|---|---|
| Address | https only, port 443 only, no user name or password; a fragment (`#...`) is dropped. Stored and used in its ASCII (IDNA) form. See the SSRF rules below. May carry a query (some receivers put a token there), so the address is **sealed** at rest like the secret (bound to the workspace, the webhook and its purpose). Only the host is kept in clear. The list shows the host only; the owner-facing detail read (`workspace.manage`) and the delivery job are the only places it is opened. Never logged or queued. |
| Questions | Which questions are sent and the name each gets in the body (`^[A-Za-z_][A-Za-z0-9_]{0,63}$`, unique). Hidden fields can be sent too. File questions cannot (webhooks never carry files); calculated values can; a repeating group is one list. A multiple choice answer is a list of the chosen options' texts. |
| Secret | Generated (`whsec_` + 256 random bits), shown **once**, when the webhook is created or its secret rotated, and stored encrypted (the same credential encryption as other secrets, bound to the workspace and the webhook). No other response returns it. |
| On or off | A switched-off webhook sends nothing; a test event may still be sent to it. |

Permissions: configuring, reading the list, rotating the secret and sending a test need `workspace.manage` (owners and admins), because the answers leave
the system. Reading the delivery log and the change history needs `form.edit` or `audit.read` (editors, admins, owners and the privacy officer, who never reads
answers).

## What is sent

`POST <address>` with `Content-Type: application/json` and this body (field order as shown, no spaces):

```json
{"event":"submission","delivery_id":"<24 hex>","form_id":"<id>","response_id":"<id>","submitted_at":"2026-10-31T09:00:00Z","data":{"full_name":"…","age":36}}
```

Only the mapped questions are in `data`; nothing else about the response is. The answers are decrypted inside the delivery job, reduced to those
questions and sent: they are never stored, queued or logged. A **test event** has `"event":"test"`, `response_id` and `submitted_at` null and made-up values.

Headers:

| Header | Value |
|---|---|
| `X-Bettercollected-Signature` | `sha256=` + hex HMAC-SHA256 of `<timestamp>.<body>` with the webhook's secret |
| `X-Bettercollected-Timestamp` | Unix seconds when this attempt was sent |
| `X-Bettercollected-Delivery` | The delivery id, the same on every attempt: a receiver that stores it can drop a repeat |
| `X-Bettercollected-Event` | `submission` or `test` |
| `User-Agent` | `bettercollected-webhooks/1` |

### Verifying a delivery

Compute the HMAC over the timestamp, a dot and the **exact bytes** received, compare in constant time, and refuse timestamps more than a few minutes old
(that is what stops a captured request from being replayed).

```python
import hashlib, hmac, time

def verify(secret: str, headers, body: bytes, tolerance: int = 300) -> bool:
    stamp = headers["X-Bettercollected-Timestamp"]
    if abs(time.time() - int(stamp)) > tolerance:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, headers["X-Bettercollected-Signature"])
```

```js
import { createHmac, timingSafeEqual } from 'node:crypto';

export function verify(secret, headers, body /* Buffer */, tolerance = 300) {
    const stamp = headers['x-bettercollected-timestamp'];
    if (Math.abs(Date.now() / 1000 - Number(stamp)) > tolerance) return false;
    const expected = 'sha256=' + createHmac('sha256', secret).update(`${stamp}.`).update(body).digest('hex');
    const given = Buffer.from(headers['x-bettercollected-signature'] ?? '');
    return given.length === expected.length && timingSafeEqual(given, Buffer.from(expected));
}
```

Answer with any **2xx** status: the delivery is done. The reply body is read up to 4 KB and dropped; only the status code and the time taken are kept.

## Retries

6 attempts in all, with exponential backoff and jitter: waits of about 30 s, 2 min, 8 min, 32 min and 2 h (each x4, +-25%, capped at 6 h), or the
destination's `Retry-After` when that is longer (capped at one hour).

| Answer | Outcome |
|---|---|
| 2xx | delivered |
| 408, 429, 5xx, timeout, connection or TLS failure | retried, then `failed` after the last attempt |
| other 4xx | `failed` at once |
| 3xx | `failed` at once: redirects are never followed |
| the address no longer passes the guard | `failed` at once (`not_allowed`) |

Timeouts: 5 s to connect, 10 s per read or write, 20 s in all. Every attempt of one delivery uses the same delivery id and the same body. A delivery is
bound to the host it was queued for (the one the respondent was shown): if the webhook's address points to another host by the time an attempt runs, the delivery is cancelled (`destination_changed`) and nothing is sent, also for a retry. It is idempotent on its (webhook, response) pair: a repeated hand-off from the submit path never queues it twice, and a queued job is claimed atomically, so two
workers never send one delivery at the same time. A submission that was erased before the send is never sent (erasure wins over a late delivery). A pending
delivery whose job was never queued, or whose worker died, is queued again by a sweep every 5 minutes.

## SSRF guard

Applied when the address is saved, again when a webhook is switched on, and **at every connection**:

- https only; port 443 only (anything else would reach services that were never meant to be called from here); no user name or password; a fragment is dropped (it is never sent to a server); no dot
  segments or encoded slashes in the path; no whitespace, control characters or backslashes;
- an internationalised host is converted to its ASCII (IDNA) form first, so what is checked, stored and connected to is one name; a host that does not
  convert is refused;
- no IP address as the host in any spelling (dotted, decimal, hex, octal, IPv6), no single-label host, no local-only suffix (`.local`, `.internal`,
  `.localhost`, `.home.arpa`, ...);
- the name is resolved by us and **every** answer must be a public address. Refused: private (RFC 1918), loopback, link-local (the cloud metadata addresses
  169.254.169.254 and fd00:ec2::254 included), carrier-grade NAT (100.64.0.0/10), unique-local and site-local IPv6, multicast, reserved, documentation,
  benchmarking and unspecified ranges, and every one of those inside an IPv4-mapped, 6to4, NAT64 or Teredo IPv6 address;
- the connection goes to the address that was checked (so a second DNS answer cannot send it elsewhere: DNS rebinding), while TLS still verifies the
  certificate against the host name (SNI and `Host` unchanged);
- no redirects, no cookies, no proxy settings, no compression; the reply is read up to 4 KB and dropped.

The rules live in `backend/backend/app/services/safe_http.py` (shared with the other outgoing calls of the backend) and
`backend/backend/app/services/webhooks/guard.py`. There is no setting that relaxes them, and no plain-http mode.

## The delivery log (action log)

One row per delivery (one per enabled webhook and submission, plus one per test event): ids (workspace, form, webhook, response, delivery), the action type
(`webhook`), a status (`pending`, `in_progress`, `retrying`, `delivered`, `failed`, `cancelled`), the HTTP status, the number of attempts and timings
(first and last attempt, the next one, when it finished, how long the last attempt took). **No answer content, no request or response body, no address, no
secret**; an error is one of our codes (`http_4xx`, `http_5xx`, `timeout`, `unreachable`, `tls_error`, `redirect_refused`, `not_allowed`, `invalid_url`,
`too_large`, `secret_unreadable`, `url_unreadable`, `answers_unreadable`, `disabled`, `destination_changed`, `internal_error`).

Rows are kept **30 days**; a job on the `webhooks` queue deletes older ones daily at 03:41. The rows of a form or workspace that is deleted go with it. The
form's settings tab has a "Deliveries" view of the log (English and Dutch) for people who may read it.

Changes to a form's webhooks (created, updated with the **names** of what changed, switched on or off, secret rotated, deleted) are recorded with who and when,
never with values, addresses or secrets, and shown as "Changes" next to the deliveries.

## Privacy panel

While the switch is on and a form has an enabled webhook, the respondent's privacy panel (English and Dutch) says that the answers are also sent to the
destination, by **host name** only, and that deleting a response here does not delete the copy there. The published form carries `webhookDestination:
{"hosts": [...]}`, derived from the stored webhooks, never from a request.

## Where it runs, and what it cannot reach

- Job `deliver_webhook`, plus the sweep `webhooks_redefer` and the purge `purge_action_logs`, on the queue **`webhooks`** of the Postgres job queue, in the
  backend's jobs worker (`python -m backend.jobs.worker`, which now consumes `default,webhooks`; override with `JOBS_QUEUES`: if you set it, include `webhooks`, or deliveries stay queued; the worker logs a warning at start when webhooks are on and it does not serve the queue). The job's only argument is the
  delivery id.
- The actions executor, which runs creator code, connects as `bc_jobs_exec`. Its row-level security policy limits it to `run_action` rows of the `actions`
  queue, so it cannot see, change, cancel or queue a webhook job, nor take a lock name that blocks one. `tests/app/jobs/test_executor_role.py` proves it
  against a real database.

## Limits and abuse

- 5 webhooks per form; 100 questions per webhook; bodies up to 1 MB.
- Test events: 5 per webhook and 20 per workspace per minute, so one webhook cannot use up the workspace's budget; address checks (create, address edits, switching on, each of which resolves the name): 30 per workspace per minute, so the
  answers "not public" / "does not resolve" cannot be used to probe names in bulk (429 `rate_limited` with `Retry-After`).
- Rotating a secret has **no grace period**: the old one stops working at once. Deliveries are signed when they are sent, so one that was queued earlier is signed
  with the new secret. Update the receiving system right after rotating.
- The delivery's attempt count is the log row's own, so a job queued afresh (after the switch was off, or by the sweep) never gives a delivery more than 6 attempts.
- The destination can learn that a submission happened and the mapped answers, nothing else. The creator learns only a status code, a time and one of our
  codes, never a reply: a webhook is not a way to read an internal service.
- Deliveries are sent by at most `JOBS_CONCURRENCY` (default 4) at a time per worker, each bounded to 20 s.

## API (workspace staff, camelCase)

| | |
|---|---|
| `GET /workspaces/{ws}/webhooks/status` | `{"enabled": bool}` (any member) |
| `GET /workspaces/{ws}/forms/{form}/webhooks` | the form's webhooks: host, questions, state (no secrets, no addresses) |
| `GET .../webhooks/{id}/detail` | one webhook with its address opened (to edit it); `workspace.manage` |
| `GET .../webhooks/variables` | the form's questions that can be mapped |
| `POST .../webhooks` | `{url, fields:[{source,key}], enabled}` -> 201 with `secret` (once) |
| `PATCH .../webhooks/{id}` | `{url?, fields?, enabled?}` |
| `DELETE .../webhooks/{id}` | 204 |
| `POST .../webhooks/{id}/rotate-secret` | a new `secret`, once; the old one stops working at once |
| `POST .../webhooks/{id}/test` | queues a real, signed delivery of sample data; returns its log row |
| `GET .../webhooks/deliveries?status=&limit=&offset=` | the delivery log |
| `GET .../webhooks/audit` | the change history |

Not (yet) on the public API or the MCP server.
