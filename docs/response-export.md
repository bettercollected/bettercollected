# Exporting a form's responses

The **Export CSV** button on a form's responses page asks the server for the file. Nothing
decrypts a whole form in the browser any more.

## Routes

All under `/workspaces/{workspace_id}/forms/{form_id}/exports`, all needing `response.export`
(Owner, Admin and Editor; Reviewers and Viewers only with an export grant; never a Privacy
officer). An export belongs to the person who asked for it: nobody else reads its status or
its file.

| Route | What it does |
|---|---|
| `GET /columns` | The columns an export may be limited to: `key`, `label`, `kind`. |
| `POST /` | Starts an export. Body (all optional): `columns` (keys), `submittedFrom`, `submittedTo` (UTC instants), `respondent` (`anonymous` or `known`), `formVersion` (list), `search` (responder email). Up to 5,000 matching responses: **200** and the file itself. More: **202** and the export to follow. |
| `GET /` | The caller's own exports of the form that are running, ready or failed. |
| `GET /{export_id}` | State of one export; once its file is ready, `downloadUrl`, a fresh signed link. |
| `GET /{export_id}/download?token=` | The file, once. |

Errors: `unknown_column` and `no_columns` (422), `rate_limited` (429, `Retry-After`),
`export_in_progress` (409), `too_many_rows` (413), `invalid_link` (403), `link_expired`,
`export_gone` (410), `download_in_progress` (409).

## The file

The same columns and cell formats as the browser's builder wrote (`services/response_export/table.py`;
`tests/app/response_export/test_table.py` pins it with that builder's output): the responder,
one column per answered question, the form's internal (staff) fields, then at the end the
response id, the submission time (UTC, ISO 8601) and one column per declared hidden field.
Answers to questions that logic hid or that were skipped stay stored and are exported as before.
Cells starting with `=`, `+`, `-` or `@` (after any whitespace), or a tab or carriage return, get
a leading apostrophe, except plain negative numbers; the headers too. Responses without answers
(deletion-only stubs) are not exported.

A form with a repeating group exported as `rows` comes as a ZIP: the main CSV and one CSV per
group table, written by one pass each, so no table is held in memory and no answer touches disk.
CSV only: there is no XLSX writer in the dependencies. The Google Sheets action keeps its own
formatting (`temporal/actions-executor/utilities/form.py`).

## Streaming and jobs

* `STREAM_MAX_ROWS` (5,000): the CSV streams in the response; responses are decrypted 500 at a
  time. Nothing is stored.
* Above it, the export is a job (`build_response_export(export_id)`, `default` queue, the backend's
  jobs worker). The filters wait sealed on the export row and are removed when the job ends. The
  job reads the live rows when it runs and asks again whether the requester still holds
  `response.export`.
* `MAX_ROWS` (100,000) and `MAX_FILE_BYTES` (256 MiB) bound one export.
* `response_export_redefer` (every 5 minutes) queues exports whose job never got queued and takes up
  those whose worker died (three attempts, then `worker_lost`).

All limits are constants in `services/response_export/limits.py`.

## The stored file

Only a job stores a file: **encrypted chunks** in `response_export_chunks` (the responses' keyset;
the context names the workspace, form, export, chunk index and requester, so a chunk opens only as
itself). It is deleted

* at its **first complete download** (an interrupted one releases the claim; one reader at a time),
* **24 hours after it was built** (`response_export_purge`, hourly; the status and the download
  also refuse an expired file),
* and **at once** when responses of the form are deleted by any route (erasure, retention, staff,
  provider sync): a running job throws its file away (`responses_deleted`).

## The link

`<expiry>.<HMAC-SHA256>` over the export id, workspace, form, the requester's id and the expiry,
under a key derived from the server's secret with its own label. It lives five minutes and is
issued again on every status read while the file is ready. It is not a credential on its own: the
download also needs the requester's sign-in, a link made for another export or user is refused, and
the permission is checked again.

## The audit entry

One `response_exports` row per export, streamed or job (kept as long as the form): who (user id),
when, workspace, form, kind, status, expected and written rows, the column keys, the filters (the
search text only as `"search": true`), file size and, for a job, when it was built, downloaded or
deleted. No answer, no file name of a respondent, no search text. It is deleted with the form or
workspace. Nothing in the product reads these entries yet.

## Rate limit

10 requests per user and form per hour, one unfinished job per user and form.
