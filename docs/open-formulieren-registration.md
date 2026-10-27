# Registration of submissions in a case system

A form built here can send each submission, as it arrives, to a case system or any other service that accepts a
JSON document (**Generic JSON**), or create an object in an **Objects API** (see "Objects API" below). The Generic
JSON format is the one Open Formulieren's "Generic JSON registration" sends, so a receiver built for
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
`secret_unreadable`, `answers_unreadable`, `file_missing`, `disabled`, `internal_error`, and for an Objects API
`lookup_failed`) and the HTTP status. Never answers, the body, the
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

## Objects API

A service of kind **Objects API** creates one object per submission in an
[Objects API](https://github.com/maykinmedia/objects-api) (the register Open Formulieren's "Objects API registration"
writes to). The same switch (`OPEN_FORMULIEREN_REGISTRATION`), job, retry schedule, address rules and delivery list
apply. What differs:

### Setup

1. In the Objects API, create an **object type** (in the Objecttypes API) whose JSON schema allows the keys you map and
   the reference key below, and a **token** for this service with **read and write** permission on that object type.
   Read is needed for the duplicate check (below); write creates the objects.
2. In the workspace, add a service of kind `objects_api`:
   - **Address**: the Objects API's base address, for example `https://objects.example.org/api/v2/`. https, port 443,
     no credentials, public addresses only, checked when saved and at every connection. We append `objects`.
   - **Object types address**: the base all of this service's object type URLs must sit under, for example
     `https://objecttypes.example.org/api/v2/`. https, port 443, no credentials, public on resolve (checked when
     saved). We never connect to it: the Objects API does.
   - **Token**: sent as `Authorization: Token <token>`. Write-only, sealed like every service secret. `none` and
     `basic` authentication are refused for this kind.
   - **Organisation name**: shown to respondents, as for Generic JSON.
   Only workspace owners and admins can set these. Changing the address needs the token again; changing the object
   types address does not.
3. On the form, choose the service and set:
   - the **object type URL** (https, at most 1000 characters, no credentials, query or fragment, ending in
     `/objecttypes/<uuid>`). It must sit under the service's object types address: same scheme and host and a path
     under it, compared after normalisation, so `..`, encoded characters, user-info tricks and look-alike hosts are
     refused (`object_type_outside_base`, `invalid_object_type_url`). A form editor cannot point it elsewhere. It is
     only sent as a value; we never fetch it. It is checked again at every send, so changing the service's object
     types address later stops sends for a form that is now outside it (`config_invalid`).
   - the **object type version** (a whole number from 1 to 10000);
   - the **mapped answers**, each with a **target path** in `record.data`: 1 to 8 names of letters, digits and `_`,
     starting with a letter, at most 64 characters, without `__` or a trailing `_`; unique, and none inside another.
     Only mapped answers are sent. **File questions cannot be mapped** (`variable_not_supported`): there is no
     Documents API here. Multiple choice answers are sent as a list of the chosen options; unanswered questions are
     left out of `data`;
   - the **reference path** (default `bettercollected_reference`), the key in `record.data` that holds the delivery's
     reference. It follows the same rules and may not clash with a mapped path. The object type's schema has to allow
     it.
4. Press **Check connection** (`POST .../forms/{form}/registration/test`, admins only): it uses the saved settings, asks the Objects API for a
   reference that cannot exist and expects `200` with no results, then asks once with a deliberately malformed filter
   and expects `400`. Together they show that the address, token, read permission and the filter work, and that the
   server really looks at the filter (an empty object type would otherwise hide an ignored filter). It reads no
   records and creates nothing. Codes: `lookup_failed` (a 4xx, for example no read permission, or an answer we cannot
   read), `filter_not_supported`, `not_configured`, `secret_unreadable`, and the transport codes. Testing a service
   itself answers `use_form_check`: a test record would create an object.

### The record

`POST <address>/objects` with `Content-Crs: EPSG:4326` and this body (Open Formulieren 4.0.6:
`contrib/objects_api/clients/objects.py:5-18`, `contrib/objects_api/typing.py:6-15`):

```json
{"type": "<object type URL>", "record": {"typeVersion": 3, "data": {"person": {"name": "Ada"}, "bettercollected_reference": "<uuid>"}, "startAt": "2026-10-27"}}
```

- `data` holds only the mapped answers, nested by their target paths, plus the reference.
- `startAt` is the submission date in Europe/Amsterdam (UTC would be a day early between midnight and 02:00).
- `geometry` is never sent, and no files.
- The reply is read up to 64 KB, only the object's `uuid` is taken from it (kept as the delivery's `remoteId`) and the
  rest is dropped. A reply that is oversized or unreadable still counts as delivered: the object exists.
- A `400` (the data does not fit the object type's schema) is permanent: `failed`, `http_4xx`. Other errors follow
  the Generic JSON rules above.

### No duplicate objects

Each delivery has a **reference**: a UUID derived from the delivery's id (no personal data, the same on every attempt),
written into `record.data` at the reference path.

Before **every send after the first** (an automatic retry, or a retry an editor asked for) the job asks the Objects
API whether an object with that reference exists:

```
GET <address>/objects?type=<object type URL>&data_attr=<reference path joined with __>__exact__<reference>&date=<startAt>&pageSize=1
```

The query is built only from the stored, validated settings and our own ids; no answer reaches it.

- **The filter parameter is `data_attr`.** The Objects API 3.x documents `data_attrs` as deprecated in favour of
  `data_attr` (one `key__operator__value` expression per parameter, nested keys joined with `__`). The manual run
  used the pinned images listed in the PR; a version that only knows `data_attrs` ignores `data_attr`, which the
  connection check and the content check below both catch. `date` is the record's own `startAt`: without it the
  Objects API lists only records that started today.
- **A hit is never trusted on its count.** On a hit we read the returned object's `record.data` at the reference path
  and require it to equal our reference. Only then is the delivery `delivered` (with that object's UUID) and nothing
  is sent. A hit that does not carry our reference, or whose data cannot be read, an answer that is not a list of
  objects, and an oversized or malformed answer all give `failed` with `lookup_failed`: never `delivered`, never a
  blind send. An Objects API that ignores the filter therefore cannot make a delivery look delivered.
- **No hit** (an empty list): the object is sent.
- **The lookup itself fails**: a connection problem, timeout, 5xx, 408 or 429 is retried later like a send. Any other
  4xx (no read permission, an unsupported filter) is `failed` with `lookup_failed`. A redirect, a refused address and
  the other safety refusals keep their own codes.

The remaining edge: if the Objects API indexed a just-created object late, a lookup could miss it and the retry would
create a second object. The first retry comes a minute after the failed attempt at the earliest, which is normally
long enough.

**The settings of the first send are kept.** The first time a delivery is about to be sent, the delivery row records
the service, its host, the object type URL, the version and the reference path (configuration only). Every later
lookup and send of that delivery uses those, so an admin editing the form between two attempts cannot move the lookup
key and cause a second object. If that service no longer exists, its address moved to another host, or its object
types address no longer holds the object type, the delivery fails with `config_invalid` instead of being sent anywhere
else (a retry then fails the same way; the creator re-submits through the destination's own process, or the admin
puts the old settings back). The lookup date is the submission's own creation time: a submission without one fails
(`internal_error`) rather than being looked up by the clock.

A lookup reply is read up to 2 MiB (a hit returns the whole stored record; every other reply is capped at 64 KB),
parsed for the little we need and dropped. Over that cap the lookup fails (`lookup_failed`).

Service addresses (both) with a `..` or `.` segment, also percent-encoded, are refused, when saved and again at every
connection. "Check connection" is limited to 10 per minute per workspace (`429`, `rate_limited`).

What we keep after a delivery: the delivery row only (ids, status, counters, timestamps, the HTTP status, the
object's UUID and the settings snapshot above), never answers, the body or the reply. It is deleted with the submission. Deleting a submission here
does **not** delete the object at the destination: that is the organisation's own process, and respondents are told
before they submit that their answers are also sent to the organisation.

### Tested against

Registration in an Objects API has been tested against a fake Objects API in the test suite and once, by hand,
against the public `maykinmedia/objects-api` 3.6.2 and `maykinmedia/objecttypes-api` 3.4.2 images on a throwaway local
stack: ten submissions delivered, one forced lost reply that the retry found without creating a second object, one
schema mismatch refused with a 400, and the connection check passing (with `data_attr`; that version also still
accepts the deprecated `data_attrs`, and refuses a malformed expression of either with a 400). It has **not been tested
against a live environment**; try it with test data first.

## Not included yet

The ZGW APIs registrations (planned), updating an existing object, payment status, the Documents API (files),
fetching the object type's schema before saving, several registrations per form, sending earlier or edited
submissions, client certificates, custom CA bundles, proxies, OAuth client credentials, the webapp screens.
