# Registration of submissions in a case system

A form built here can send each submission, as it arrives, to a case system or any other service that accepts a
JSON document. The format is the one Open Formulieren's "Generic JSON registration" sends, so a receiver built for
Open Formulieren can accept submissions from here too. This page is for the people who run the instance and the
workspace admins who set it up.

> **Not tested against a live environment yet.** Registration has been tested against a local fake server, against a
> local Open Formulieren 4.0.6 (to compare the format) and against throwaway local images. It has not been run
> against a live case system. Try it with test data and a test destination first, and tell us what you find.

Registration is behind a switch that is **off by default**. While it is off nothing is queued or sent, the settings
screens answer "turned off" (HTTP 410, code `registration_off`), and the respondent's form says nothing about it. What
was saved earlier stays in the database.

| Setting | Values | Default |
|---|---|---|
| `OPEN_FORMULIEREN_REGISTRATION` | `on`, `off` | `off` |

The switch is read live from the settings store (restart-class, see `docs/settings-inventory.md`). The deliveries are
sent by the jobs worker (`python -m backend.jobs.worker`), so the worker has to run, with
`JOBS_BACKEND__register_submission` left at its default (`postgres`).

## How it works

1. A workspace owner or admin adds a **service**: a name, an https address, how to authenticate, and the name of the
   organisation respondents are told about.
2. For a form, an owner or admin turns **registration** on, picks the service, an optional path and the **variables**
   to send. Only listed variables are sent: nothing else about the submission leaves.
3. When someone submits the form, the answers are stored as usual, a small **delivery record** is written and a
   background job is queued. The respondent's request does not wait for the destination.
4. The job decrypts that one submission, builds the body from the listed variables and posts it to the service.
5. If the destination is down or slow the job tries again (below). After the last attempt the delivery is shown as
   failed on the form's results page, with a **Retry** button for editors.

Only forms collected here can send submissions on (not forms imported from Google Forms). Only submissions made while
registration is on and enabled for the form are sent: earlier ones never are, and edits to a submission are not sent
again.

## Services

| Field | |
|---|---|
| Name | Your label, unique in the workspace. |
| Address | `https://`, default port, no user name, query or fragment. The name must resolve to public addresses only. |
| Authentication | None; a header (the header's name and a secret, for example `Authorization: Token ...` or an API key header; names the client sets itself or that steer a request, such as `Host`, `Content-*`, `Transfer-Encoding`, `Connection`, `Proxy-*`, `Accept*`, `Cookie`, `User-Agent` and `Idempotency-Key`, are refused); or basic (user name and secret). |
| Organisation name | What respondents are told (see "What respondents see"). Defaults to the workspace title. |

The **secret is write-only**. It is encrypted at rest with the credential key of the backend (`AUTH_AES_HEX_KEY`),
bound to its workspace and service, and never returned by the API, logged, put in a job or shown again; the settings
screen only says whether one is set. Changing the address or the authentication needs the secret again, so a stored
secret can't be pointed at a new host by someone who can't read it. Deleting a workspace deletes its services.

Owners and admins (permission `workspace.manage`) manage services and the choice of variables. Editors may retry a
failed delivery (`form.edit`), and members who can read responses see the delivery list.

## Which variables

A variable is a question of the form (the name is its id), a repeating group (sent as a list of items), a hidden field
(a captured URL parameter) or a calculated value. Content blocks, internal (staff-only) fields, matrices, payment and
table questions can't be sent yet. Each variable gets a **key** in the body (letters, digits and `_`, unique; by
default the variable's name).

## The body

A JSON object posted with `content-type: application/json`, with the four keys Open Formulieren sends:

```json
{
  "values": { "firstName": "Ada", "age": 36, "topics": ["news", "offers"], "attachment": { "file_name": "note.txt", "content": "<base64>" } },
  "values_schema": { "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "properties": { "...": {} }, "required": ["..."], "additionalProperties": false },
  "metadata": { "public_reference": "9f1c...", "form_version": "3", "registration_timestamp": "2026-10-27T08:15:00Z" },
  "metadata_schema": { "...": "..." }
}
```

- `values_schema` describes `values` (informative, not for validation); `metadata` carries `public_reference` (the
  submission number the respondent sees), `form_version` and `registration_timestamp` (UTC, whole seconds).
- Text questions that were not answered are `""`; numbers, dates and yes/no questions are `null`. Files are
  `{file_name, content}` with the content base64 encoded, or `null`. A multiple choice question is an object of option
  to true/false (or a list of the chosen options when "send as a list" is set). A choice is the option's text as the
  respondent saw it.
- Headers: the authentication header, `Idempotency-Key` (the delivery's id) and a fixed `User-Agent`.

Where we follow the format and where we differ is checked against bodies captured from a real Open Formulieren 4.0.6
(`backend/tests/fixtures/registration/`). Deliberate differences: an unanswered yes/no is `null` (they send `false`)
and, for values that are `null`, our schema says so (`["number","null"]`); a question that takes several files is not
supported (a file question here holds one file); the metadata is the fixed three (their extra metadata variables are
not offered yet).

Limits: the whole body at most 20 MB, at most 20 files, each at most 10 MB, all files together at most about 15 MB (checked while the body is built, so a job never holds more than that). Files are read only from the submission's own storage folder. A submission over a limit fails as
`too_large` and is not truncated.

## Delivery, retries and failures

At most six attempts, waiting 1 minute, 5 minutes, 30 minutes, 2 hours and 6 hours between them (about 8.6 hours).
A `Retry-After` of the destination up to one hour is honoured. Transient failures are retried: connection errors,
timeouts, TLS errors, 5xx, 408 and 429. These are **not** retried: other 4xx, a refused address, a redirect, a body
over the limit, a missing file, an unreadable secret or answer. After the last attempt the delivery is `failed`; an editor can
press Retry, which starts the schedule again.

A delivery waiting for a retry when the switch is turned off goes back to pending and is sent after the switch is on again. Delivery is **at least once**: if the destination processed a request but the answer was lost, the retry sends it
again. Use `metadata.public_reference` or the `Idempotency-Key` header to deduplicate.

A delivery record holds ids, a status, counters and one of our error codes (`unreachable`, `timeout`, `tls_error`,
`not_allowed`, `invalid_url`, `redirect_refused`, `http_4xx`, `http_5xx`, `too_large`, `config_invalid`,
`secret_unreadable`, `answers_unreadable`, `file_missing`, `disabled`, `internal_error`) and the HTTP status. Never answers, the body, the
address, the secret or what the destination replied. Logs name ids and codes only.

## Outbound safety

Every call: https only on port 443, no credentials in the address; the host is resolved at every connection and every
answer must be a public address (private, loopback, link-local including the cloud metadata address, multicast,
reserved, carrier-grade NAT, and the same inside IPv4-mapped, 6to4, NAT64 and Teredo addresses), and the connection
goes to the address that was checked, so a name that changes after it was saved is refused; **no redirects** (the
credential header never follows one); connect, read, write and total time limits; the reply is read up to 64 KB and
dropped. There is no setting that allows http or private addresses. The same rules (`services/safe_http.py`) are used
for fetching an image address someone pasted in the editor.

## What respondents see

While registration is on for a form, the privacy panel names where answers also go:

- English: "Your answers are also sent to {organisation}'s case system."
- Dutch: "Je antwoorden worden ook verstuurd naar het zaaksysteem van {organisation}."

The form's payload carries `registrationDestination: {"organisation": "..."}` for the webapp to show it. It is derived
from the stored configuration, never from a request.

## Deleting data

A delivery record is removed with its submission (deletion, expiry, user and workspace deletion), and a form's registration and delivery records are removed when the form is deleted (whatever the switch says); a nightly sweep
(when registration is on) removes any whose submission is gone. **What was already sent cannot be recalled**:
deleting a submission here does not delete the copy at the destination. That is the organisation's own process, and
should be said in its privacy information.

## Not included yet

The Objects API and the ZGW APIs registrations (planned), several registrations per form, sending earlier or edited
submissions, client certificates, custom CA bundles, proxies, OAuth client credentials, the webapp screens.
