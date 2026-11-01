# Submitting responses through the API

An API key with the `submissions:write` scope can create responses and change
the ones it made, from your own system (a back office, an import, a kiosk).
It is part of the [public API](api/README.md) and is **off by default**:
the server setting `SUBMISSIONS_API_ENABLED` turns it on (see the
[settings inventory](settings-inventory.md)). While it is off, both endpoints
answer 404, an API key can't be created with the scope, and a key that has it
is refused. Responses made through the API stay where they are.

## What it does and does not do

A submission through the API goes through **the same code a respondent's
submission goes through**. Nothing is checked twice or differently:

- only the **published** version of the form counts (a form that was never
  published takes no responses, a draft change that is not published yet does
  not apply);
- a closed form, a form that has not opened yet and a form that has received
  all the responses it accepts refuse with 409 (`form_closed`,
  `form_not_open`, `form_full`);
- the answers are checked as a respondent's are: types, required questions
  (with the pages a respondent would go through), patterns, number and date
  rules, field rules, choice logic; calculated values are the server's, never
  yours;
- the retention the form states is applied (and the expiry job scheduled);
- the answers are encrypted at rest with the response keyset;
- actions, webhooks, email actions and registrations run as they do for a
  respondent's submission.

What is different, on purpose:

- **A key is not a respondent.** No identity is stored with the response, no
  receipt number or receipt email goes anywhere, nothing is sent to an email
  address. Because the response belongs to no signed-in person, the respondent
  can't find it by signing in (self-service access, edit and deletion by
  sign-in); the people who run the form handle such requests, as they do for
  any anonymous response. Forms that ask for a verified respondent, and private forms, refuse
  API submissions (422 `respondent_identity_required`).
- **You assert the consent.** A form with a consent step (every form that has
  not removed it) needs `"consent": true` in the body: you state that the
  respondent has given the consent the form asks for. The stored consent is
  built by the server from the form's own items; the response records that the
  key asserted it. Without it: 422 `consent_required`.
- **The source is recorded** (`api`, the key's name, whether consent was
  asserted). Staff see it on the response page; respondents never do. A
  webhook body carries `"source": "api"` for such a response (and has no
  `source` for a respondent's); the key itself never leaves.
- **No files, signatures or payments yet.** A question that takes one of them
  answers 422 `invalid_answers` with the rule `question_not_supported`, and
  the raw file and signature answer slots are refused on every question. A form
  with a required file or signature question can't be completed through the API.

## Endpoints

Base `https://<your instance>/api/v1/public/v1`, `Authorization: Bearer bc_...`,
scope `submissions:write` (also listed in the [API reference](api/README.md)).

### `POST /forms/{formId}/submissions`

```json
{
  "answers": {
    "name": "Ada Lovelace",
    "dinner": true,
    "meal": "Fish",
    "age": { "type": "number", "number": 36 }
  },
  "hiddenFields": { "utm_source": "crm" },
  "consent": true
}
```

Answers `201`:

```json
{ "responseId": "…", "formId": "…", "submittedAt": "2026-11-01T10:00:00+00:00", "formVersion": 3 }
```

- `answers` is keyed by **question id** (the `id` of the question in the form's
  spec document, and the key of `answers` in `GET .../responses/{id}`). A
  value is either
  - the typed answer object a response read returns (so what you read can be
    written back): `{"type": "text", "text": "Ada"}`,
    `{"type": "choice", "choice": {"value": "<option id>"}}`, and so on; or
  - a shorthand: text for a text, email, url, phone, date, day or time
    question; a number for a number, rating or scale question; `true` or
    `false` for yes/no; an option's id or its text for a choice (a list for a
    multiple selection); a list of texts for tags; an object for a currency,
    date range or address; a list of objects for a repeating group. Other
    kinds (matrix, ranking, table) take the typed object.
  `null` leaves a question unanswered.
- `hiddenFields` are values for the form's declared hidden fields; names the
  form does not declare are left out.
- Nothing else is accepted: a body with another member (an owner, a source, a
  retention, an ending, a time) is 422 `invalid_request`.

### `PATCH /forms/{formId}/submissions/{responseId}`

```json
{ "answers": { "dinner": false } }
```

Partial: the questions sent replace their stored answers, the others stay;
same value shapes, same checks as a respondent's own edit (against the form's
latest published version, for what the edit touches). Answers `200`
`{"responseId": "…", "updatedAt": "…"}`. **A key can only change a response it
made itself** (404 for any other: a respondent's, another key's, an imported
one). As for a respondent's edit, the form's open and close dates and response
limit do not apply to an update.

## Errors

The API's usual shape, `{"code", "message", "errors"?: [{"path", "message"}]}`.
Problems with answers are `422 invalid_answers`, one entry per problem, `path`
a JSON pointer into your body and `message` starting with the rule's code:

```json
{
  "code": "invalid_answers",
  "message": "Some answers are missing or not valid.",
  "errors": [
    { "path": "/answers/name", "message": "required: this question needs an answer" },
    { "path": "/answers/age", "message": "too_small: the number is below the minimum" }
  ]
}
```

Rule codes: `required`, `too_short`, `too_long`, `pattern`, `too_small`,
`too_large`, `not_integer`, `too_few_choices`, `too_many_choices`, `format`,
`currency`, `range_order`, `duplicate`, `type`, `choice`, `unknown_field`,
`question_not_supported`.

Other codes: `form_not_allowed` (403: the key is limited to other forms),
`missing_scope` and `key_creator_lacks_permission` (403), `consent_required`,
`respondent_identity_required` (422), `form_closed`, `form_not_open`,
`form_full` (409), `rate_limited` (429, with `Retry-After`).

## Keys

Create the key on the dashboard's **AI → MCP** tab. The `submissions:write`
scope is offered only while the server has the feature on, and is never
implied by another scope (not even `forms:write`). A key can be limited to
some of the workspace's forms (`submissionFormIds` when created through the
API); with no list it may submit to every form of its workspace. The creator
must still be able to read forms (`form.read`): a key never outlives its
creator's membership.

## Retries, limits and audit

- `Idempotency-Key` (on both endpoints): the same key and the same request
  within 24 hours returns the first answer, marked `Idempotent-Replayed:
  true`, and nothing runs twice; the same key with another request is 422
  `idempotency_key_reused`; while the first is still running, 409
  `idempotency_in_progress`. Only a summary (the status and the response id) is
  kept, never an answer.
- Submissions count against their **own** rate budget per key and per
  workspace (the same ceilings as reads, `API_PUBLIC_API_REQUESTS_PER_WINDOW`
  and `API_PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW`): reads never use it up,
  nor the other way round.
- Every write is one row in the workspace's API audit log: the key, the
  operation, the status, the form id and the response id. Never an answer.

## SDKs and the command line

```python
from bettercollected import BetterCollected

with BetterCollected(api_key, "https://forms.example.org") as bc:
    created = bc.create_submission(
        form_id, {"name": "Ada", "dinner": True}, consent=True, idempotency_key="order-1042"
    )
    bc.update_submission(form_id, created.response_id, {"dinner": False})
```

```ts
const created = await client.createSubmission(formId, { answers: { name: "Ada" }, consent: true });
await client.updateSubmission(formId, created.responseId, { name: "Ada L." });
```

```bash
bettercollected submit <form-id> answers.json --consent --idempotency-key order-1042
bettercollected update-submission <form-id> <response-id> answers.json
```

`answers.json` holds `{"answers": {...}}` (and optionally `hiddenFields`);
consent is asserted on the command line, never from the file.
