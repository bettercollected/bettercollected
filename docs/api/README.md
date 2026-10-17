# Public API v1

A REST API for working with forms as code: create, read, change and publish
forms as [form spec v1](../spec/README.md) documents, and read their
responses. It offers the same things as the MCP server and runs on the same
services.

- Base URL: `https://<your instance>/api/v1/public/v1`
- OpenAPI document: [`public-v1.openapi.json`](public-v1.openapi.json), also
  served at `/api/v1/public/v1/openapi.json` (interactive docs at `/docs`)
- SDKs: [`sdk/typescript`](../../sdk/typescript) and
  [`sdk/python`](../../sdk/python) (with the `bettercollected` command line
  tool)

## Authentication

Send a workspace API key as a Bearer token:

```
Authorization: Bearer bc_...
```

A workspace admin creates keys under the workspace's API key settings. A key
works in its own workspace only. Cookies are never read, so a browser session
cannot be used against this API.

| Scope | Allows | The key's creator must hold |
|---|---|---|
| `forms:read` | list, read and validate forms | `form.read` |
| `forms:write` | create, replace, edit and publish forms | `form.edit` |
| `responses:read` | list and read responses | `response.read` and `response.export` |

The creator's permissions are checked on every call: a key never does more
than the person who created it may do at that moment. Every call is recorded
in the workspace's API audit log.

## Endpoints

| Method and path | What it does |
|---|---|
| `GET /forms?page&size` | The workspace's forms, paginated |
| `POST /forms` | Create a draft from a whole document (all or nothing) |
| `POST /forms/validate` | Check a document; stores nothing |
| `GET /forms/{formId}` | The form as a document, with an `ETag` |
| `PUT /forms/{formId}` | Replace the form from a document; needs `If-Match` |
| `POST /forms/{formId}/replace/dry-run` | What a `PUT` would store, and the diff |
| `POST /forms/{formId}/ops` | Apply edit operations (atomic by default) |
| `POST /forms/{formId}/ops/dry-run` | Preview operations; stores nothing |
| `POST /forms/{formId}/publish` | Publish, with the product's publish checks |
| `GET /forms/{formId}/responses?page&size` | Response summaries, most recent first |
| `GET /forms/{formId}/responses/{responseId}` | One response with its answers |

### Replacing a form

`PUT` replaces the form's content: title, welcome page, pages and their
fields, endings, theme, hidden fields and section titles. In `trust` and
`logo`, a key you leave out keeps its stored value; send `""` to clear a
text. The logo image is set by uploading it in the product; a `logo.url` in
a document is ignored.

### Versions

`GET /forms/{formId}` answers an `ETag`. Send it back as `If-Match`:

- `PUT` requires it: 428 without, 412 when the form changed since. The write
  itself is conditional, so a save that lands at the same moment also gives
  412, never a lost update.
- `POST .../ops` accepts it: when given, a stale one gives 412.

Successful writes answer the new `ETag`.

### Operations

The operations are those of the MCP `update_form` tool (`add_field`,
`update_field`, `move_page`, `set_field_validation`, ...), with client
references: an op that creates a page or field takes `"ref": "<name>"`, and
later ops in the same batch use `"$ref:<name>"` as its id. At most 200
operations per batch. With `atomic` (the default here), any failed
operation is a 422 `ops_failed` listing every failure, and nothing is
stored.

### Responses

Only the workspace's own responses are returned. A response with a pending
deletion request carries `deletionRequest: {"status": "pending"}`; honour it
in every copy you keep. Who answered (email, identity) and captured URL
parameters are never returned. Values of internal (staff-only) fields are
returned as `internalAnswers`.

## Retries

`POST /forms`, `POST .../ops` and `POST .../publish` accept an
`Idempotency-Key` header (1 to 255 printable characters). Within 24 hours,
the same key with the same request (method, path and body) returns the first
response with `Idempotent-Replayed: true` and runs nothing again; the same
key with a different request is refused with 422 `idempotency_key_reused`.
Keys are per API key.

## Limits

- Requests per API key: 120 a minute by default
  (`API_PUBLIC_API_REQUESTS_PER_WINDOW`, `API_PUBLIC_API_WINDOW_SECONDS`);
  beyond that 429 with `Retry-After`.
- Request bodies: at most 1 MB (413). A document has at most 200 pages and
  2000 fields.

## Errors

Every error has one shape:

```json
{
  "code": "invalid_spec",
  "message": "The document is not a valid form spec.",
  "errors": [{ "path": "/pages/0/fields/1/type", "message": "..." }]
}
```

`code` is stable and meant for programs; `path` is a JSON pointer into the
request body.

## Changing the API

The OpenAPI document is generated from the code. After changing an endpoint
or its models, regenerate it from `backend/`:

```bash
uv run python -m backend.app.public_api.openapi
```

A test fails when the committed file is out of date. Then regenerate the
SDK types (see each SDK's README).
