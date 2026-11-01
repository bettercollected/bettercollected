# Exporting a form's responses

The **Export** button on a form's responses page asks the server for the file, as CSV, Excel
(`.xlsx`) or JSON. Nothing decrypts a whole form in the browser any more. A single response also has
a **PDF** (see "The PDF of one submission").

## Routes

All under `/workspaces/{workspace_id}/forms/{form_id}/exports`, all needing `response.export`
(Owner, Admin and Editor; Reviewers and Viewers only with an export grant; never a Privacy
officer). An export belongs to the person who asked for it: nobody else reads its status or
its file.

| Route | What it does |
|---|---|
| `GET /columns` | The columns an export may be limited to: `key`, `label`, `kind`. |
| `POST /` | Starts an export. Body (all optional): `format` (`csv`, the default, `xlsx` or `json`), `columns` (keys), `submittedFrom`, `submittedTo` (UTC instants), `respondent` (`anonymous` or `known`), `formVersion` (list), `status` (deletion-request status: `none`, `pending`, `declined`, `success`), `search` (responder email). Up to 5,000 matching responses: **200** and the file itself. More: **202** and the export to follow. |
| `GET /` | The caller's own exports of the form that are running, ready or failed. |
| `GET /{export_id}` | State of one export; once its file is ready, `downloadUrl`, a fresh signed link. |
| `GET /{export_id}/download?token=` | The file, as often as wanted until it is deleted. |
| `DELETE /{export_id}` | Deletes a ready file now (requester only, 204; also when it is already gone, 409 `export_not_ready` while it is still being built). The audit entry stays. |

Errors: `unknown_column`, `no_columns`, `unknown_format` and `too_many_columns` (xlsx only, 422), `rate_limited` (429, `Retry-After`),
`export_in_progress` (409), `too_many_rows` (413), `invalid_link` (403), `link_expired`,
`export_gone` (410), `export_ready` (409), `workspace_busy` (429), `export_busy` (429),
`export_not_ready` (409).

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
The passes are separate reads of the live responses, not a snapshot: a response submitted or deleted
between two of them can appear in one table and not the other. The audit entry's row count is that
of the main table.

## Formats

`format` is a parameter of the one request path: the permission, rate limit, row cap, stream slots,
job, encrypted chunks, signed link, deletion and audit entry are those described in this document for
every format, and the columns and filters choose the same responses and the same columns. The audit
entry's `format` says what was written: `csv`, `zip` (a CSV export of a form with repeating groups as
tables), `xlsx` or `json`. A job carries the format sealed with its filters; a job queued before formats
existed has none and builds a CSV.

**XLSX** (`services/response_export/xlsx.py`). One sheet `Responses` and one sheet per repeating group
exported as `rows` (the tables of the CSV archive), written by a streaming writer of our own into a ZIP
that is never seekable: no table in memory, no answer on disk (a spreadsheet library would need a file to
seek in). It has no way to write a formula, macro, defined name or external link.

* Text is written as typed text, so Excel and LibreOffice never evaluate it. A string that the CSV guard
  would prefix with an apostrophe (starts with `=`, `+`, `-`, `@` after any whitespace, or with a tab or
  CR) is kept as the respondent wrote it and carries Excel's own "this is text" flag (`quotePrefix`), so it
  stays text if the person edits the cell. The header row has the same guard.
* The submission time (UTC) and the answers to date questions are real dates when they are ISO dates (a
  value that is not stays text). Numbers stay numbers, except integers of 16 digits or more (Excel keeps
  15): those are text.
* The file is kept openable: characters XML cannot carry are removed, the `_xHHHH_` escape Excel decodes
  inside strings is escaped, text over Excel's 32,767 characters is cut, sheet names follow Excel's rules (31 UTF-16 units).
  A sheet cannot hold more than 1,048,576 rows: a job whose repeating-group table would pass it fails with
  `too_large`. More than 16,384 columns is refused (`too_many_columns`).
* The header row is bold, frozen and filterable.

**JSON** (`services/response_export/json_export.py`). One UTF-8 document, streamed:

```json
{"form": {"id": "...", "title": "..."},
 "questions": [{"key": "...", "id": "...", "title": "...", "type": "...", "choices": [{"id": "...", "label": "..."}]}],
 "responses": [{"responseId": "...", "submittedAt": "2026-10-01T10:00:05Z", "formVersion": 1, "responder": "...",
                "answers": {"<question id>": {"type": "text", "text": "..."}},
                "internalAnswers": {}, "hiddenFields": {}}]}
```

The shape is close to the REST API's response: the same names (`responseId`, `submittedAt`, `answers` keyed by
question id with the stored answer objects, `internalAnswers`) and the same answer objects, plus `questions` so the
ids can be read and `formVersion`. The differences: `submittedAt` ends in `Z` (the CSV's form) where the API writes
`+00:00`, and `responder`, `internalAnswers` and `hiddenFields` appear only when their columns are chosen (the API
never returns who answered). Only the selected
columns appear (`responder`, `internalAnswers` and `hiddenFields` only when chosen). A repeating group
stays nested (`{"items": [{"<child id>": ...}]}`); the `rows`/`columns` layout is a spreadsheet matter.
No link to a stored file leaves: an answer's `file_url`, a file's `url` and a drawn signature's `file_id`
and `url` are removed (the CSV never carries them either).

## Streaming and jobs

* `STREAM_MAX_ROWS` (5,000): the CSV streams in the response; responses are decrypted 500 at a
  time. Nothing is stored.
* Above it, the export is a job (`build_response_export(export_id)`, on the **`exports` queue**, which
  the backend's jobs worker serves next to `default` and `webhooks`; if you set `JOBS_QUEUES`, include
  `exports`, or large exports stay queued: the worker logs a warning at start). The queue is separate so
  it can be given a worker of its own (`JOBS_QUEUES=exports`), but a worker serving several queues shares
  one `JOBS_CONCURRENCY` between them: to keep a long export from ever waiting on a deletion, run a second
  worker for it. The executor's database role cannot see this queue. The filters wait sealed on the export row and are removed when the job ends. The
  job reads the live rows when it runs and asks again whether the requester still holds
  `response.export`.
* `MAX_ROWS` (100,000) and `MAX_FILE_BYTES` (256 MiB) bound one export (in any format): the request is refused above the row cap, and a job stops with `too_many_rows` if responses that arrived after the count push it past it (`too_large` for the file size). The Export control sends the
  responses list's filters and search, so a form above 100,000 responses is exported in parts by narrowing the list.
* **One live export per requester and form** (a job in flight, or whose file waits to be fetched: 409
  `export_in_progress` or `export_ready`), enforced by a partial unique index, so two requests at once
  make one job. **At most `WORKSPACE_MAX_JOBS` (3) jobs in flight per workspace** (429 `workspace_busy`);
  the count and the insert run under a lock on the workspace. A request refused for either reason is
  given back to the rate limit below: it does not use up the person's budget.
* **A run owns the export only while its claim is current.** Each stored chunk is written under the row
  lock together with a heartbeat (`started_at`), and refused once the export is no longer running on that
  claim; the final state is checked the same way. A job that is merely slow is therefore never taken for
  dead while it stores chunks, and if the sweep does requeue one (nothing stored for 30 minutes), the old
  run stops without touching the new run's chunks (a re-claim also clears the chunks of the run before it).
* **Streams in flight are bounded too.** A streamed export (and a bulk JSON read, below) holds a
  response open and decrypts 500 rows at a time, so at most `STREAMS_PER_USER` (2) run at once per
  requester and workspace (429 `export_busy`) and `STREAMS_PER_WORKSPACE` (6) per workspace (429
  `workspace_busy`). They are counted in Postgres, on the audit rows that are `streaming`, under the same
  per-workspace lock the jobs take, so the bound holds with several backend replicas. A stream frees its
  slot when it ends (finished or cut off). A live stream beats (`heartbeat_at`, every
  `STREAM_BEAT_EVERY`, 30 seconds, from a task of its own) while its client keeps taking pieces, and counts
  for as long as it beats. It stops beating when no piece was taken for `STREAM_SLOT_TTL` (a client that
  left, or a generator the server left open after a disconnect) and in any case `STALE_STREAMING_AFTER`
  (1 hour) after it started; a row that has not beaten for `STREAM_SLOT_TTL` (3 minutes) stops counting, and
  the sweep ends it after `STALE_STREAMING_AFTER` without a beat. A request refused because no slot was free is given back to the
  rate limit below: it does not use up the person's budget.
* **A queued job has a maximum age.** One that no worker has taken in `QUEUED_MAX_AGE` (2 hours since it
  was queued) is failed with `queue_timeout` by the hourly sweep: the Export control shows it as a failed
  export, its sealed filters are removed and the workspace's slot and the requester's open export are
  free again. (Without an `exports` worker the jobs would otherwise sit there for ever.)
* **The heartbeat has its own field.** A running job writes `heartbeat_at` with each chunk it stores and
  at least every `HEARTBEAT_EVERY` (30 seconds) while it reads rows that have not filled a chunk yet;
  `started_at` stays the time of its claim. The sweep takes a job for dead when its last heartbeat is
  older than `STALE_RUNNING_AFTER`. A row written before the field existed has none and falls back to its
  `started_at`. (The field lives in the stored document: no migration.)
* `response_export_redefer` (every 5 minutes) queues exports whose job never got queued (not those past
  their maximum age) and takes up those whose worker died (three attempts, then `worker_lost`).

All limits are constants in `services/response_export/limits.py`.

## The stored file

Only a job stores a file: **encrypted chunks** in `response_export_chunks` (the responses' keyset;
the context names the workspace, form, export, chunk index and requester, so a chunk opens only as
itself). It stays downloadable, any number of times (each download only counts in the audit entry: `downloadedAt`, `downloadCount`), and is deleted

* by its **requester**, from the Export control's "Delete the file" or `DELETE /{export_id}` (a file waiting blocks a new export of that form, so this is the way to start another before the 24 hours are over),
* **24 hours after it was built** (`response_export_purge`, hourly; the status and the download
  also refuse an expired file),
* and **at once** when responses of the form are deleted by any route (erasure, retention, staff, a
  provider sync that deleted something): **any deletion of a form's responses cancels its running jobs
  (`responses_deleted`) and erases its ready files**, whether or not the deleted response was in them
  (privacy first: nothing is checked against the file's contents). A queued job has read nothing yet and
  simply runs on what is left.

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
workspace. When an account is deleted, its rows in other workspaces stay with the user replaced by
`deleted-user` (and a file it had waiting is deleted). Nothing in the product reads these entries yet.

**Other ways the same data leaves.** `GET .../all-submissions` (every response as decrypted JSON, for
scripts) takes the same permission, shares the rate limit and writes the same audit entry (channel
`all_submissions`, format `json`). Its answer is built in memory, so it holds at most
`BULK_JSON_MAX_ROWS` (5,000) responses: a form with more is refused with 413 `too_many_rows` (the
response for smaller forms is unchanged), and the message points to the export, which takes up to
100,000. It counts as a stream in flight until its answer has been built and sent (the row is closed by a task
after the response; a failure to close it never turns a good read into an error, and the row stops
counting after `STREAM_SLOT_TTL`), and a refused or failed read leaves its row as `failed` with a code
and no rows.

Reads of responses through a **workspace API key** (the REST API's `GET .../responses` and
`.../responses/{id}`, and MCP `list_responses` and `get_response`) write the same kind of entry, one per
read: channel `api_key` or `mcp`, `actor` `api-key:<key id>` (the id only: never the key, its name or the
person who made it), the form, the number of responses returned, format `json`. No answer, no search text.
A read the key is refused, or that finds nothing, writes none; if the entry cannot be stored the read
fails instead of going unrecorded. These reads are not limited here: the REST API has its per-key rate
limit and a page is at most 100 responses.

Not covered yet (later, in the UI): narrowing an export of more than 100,000 responses.

## The PDF of one submission

`GET /workspaces/{workspace_id}/submissions/{response_id}/pdf?lang=nl|en&tz=<IANA zone>`: one response as
a PDF, drawn when asked and **never stored** (`Cache-Control: no-store`, `Content-Disposition: attachment`).
It needs `response.read` on the workspace (Owner, Admin, Editor, Reviewer, Viewer; never a Privacy officer);
the response must be the workspace's own copy, and anything else is the same 404 as the single-response
read. A respondent's own copy is not served by this route.

* **Content.** The form's title, when it was submitted (in `tz`, UTC when missing or unknown, with the zone's
  abbreviation), the responder or "Anonymous", the response id, the form version and the captured hidden
  values; then every question of the form with its answer in the text the CSV uses (multi-selects one per
  line, repeating groups as numbered items, "No answer" for an unanswered question). The form is the version
  the response records when it has one (an imported response), else the form as it is now, as on the response
  page. **Not printed:** the form's internal (staff-only) fields and the staff feedback. Files are listed by
  name and size, never embedded or linked. **A drawn signature is listed** ("Drawn signature (image not
  included)" and when it was signed), not drawn: the API process never decodes images
  (`services/signatures.py`). A typed signature prints its name.
* **Language and zone.** `lang` is `en` or `nl` (anything else is English): the labels are ours, the
  questions and answers are the form's own. `tz` is the viewer's IANA zone (the webapp sends the browser's).
* **How it is made** (`services/response_pdf/`). In the API process, in a worker thread, with ReportLab (pure
  Python) and the bundled DejaVu Sans (free Bitstream Vera licence, `fonts/LICENSE.txt`): Latin, Greek and
  Cyrillic print; scripts that need shaping or right-to-left layout (Arabic, Hebrew, Indic) and characters
  outside the Basic Multilingual Plane (emoji) print as U+FFFD. Answers are drawn as text with `drawString`
  (never as markup), control and format characters are removed, nothing is fetched, no image, link, script or
  attachment is written. This is not done in the document sandbox: the sandbox exists to *open* hostile
  files with native decoders; nothing hostile is parsed here. At most `PDF_PARALLEL` (2) are drawn at once
  in a process (a request waits `PDF_WAIT_SECONDS`, then 429 `export_busy`), an answer is cut at 20,000
  characters (`[shortened]`), and a document past 200 pages, 500,000 characters in all or 10 seconds of layout
  is refused (413 `pdf_too_large`; wrapping is linear in the text, even for one word wider than the line).
* **Tagged.** The PDF carries a structure tree (`Document` > `H1`, `H2`, `L` > `LI` > `Lbl` + `LBody`) in
  reading order, the document language and title, and its page numbers are artifacts. It has not been
  validated against PDF/UA and is not claimed to conform.
* **Limits and audit.** `PDF_REQUESTS_PER_WINDOW` (60) per user and workspace per hour, apart from the 10
  exports an hour (a reviewer reads many responses); 429 `rate_limited` with `Retry-After`. A request is
  given back only when no drawing started (no free slot, 429 `export_busy`, or a failure before it); a PDF
  refused as too large (413 `pdf_too_large`) was drawn and counts. One audit entry like an export's (channel `response_pdf`, kind
  `stream`, format `pdf`, the response id in `filters`, one row; no title, name or answer) is stored
  **before** the bytes are sent: if it cannot be stored the request fails. A request refused for 403, 404 or
  by the budget writes none. Nothing of the response is logged.

## Rate limit

10 requests per user and form per hour (exports and `all-submissions` reads together), one live export per user and form, three jobs in flight per workspace. A request refused because a slot was busy (429 `export_busy` / `workspace_busy`) or because the person's export of the form is still open (409 `export_in_progress` / `export_ready`) is given back and does not count; one refused by the rate limit itself (429 `rate_limited`) changes nothing.
