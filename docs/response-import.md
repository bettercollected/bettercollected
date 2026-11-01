# Importing responses from a CSV file

The **Import responses** button on a form's responses page adds responses collected elsewhere to
the form. It is behind the server switch `CSV_IMPORT_ENABLED` (off by default: every route answers
404 and the webapp shows no button) and needs the permission `response.import` (Owner and Admin).

The file an export of the same form wrote (`docs/response-export.md`) imports as it is: its
columns are recognised and its cells are read back exactly as the export wrote them.

## The flow

1. **File.** A `.csv` of at most 5 MiB, 5,000 data rows, 500 columns, 10,000 characters per cell and
   200 per heading, as UTF-8 (with or without a byte order mark) or Windows-1252, separated by
   `,` or `;` (detected from the heading line; an Excel `sep=;` line is honoured). A ZIP (so also an
   XLSX), a PDF, any binary or UTF-16 text is refused with a clear code. The file is the request
   body (`Content-Type: text/csv`), not a multipart form, so no framework spools it to disk.
2. **Columns.** Each column of the file is matched to a question or left out. Headings are
   matched to the export's own headings (also for staff-only `Internal: ...` and `Hidden: ...`
   columns and a repeating group's `Job 2 – Employer`), then ignoring case and spacing, then by
   question id. The responder, the response id, calculated questions and a repeating group
   exported as its own table are left out on purpose (a note says why); file uploads, drawn
   signatures, matrices and tables cannot be imported. Questions are those of the *published*
   version of the form.
3. **Check** (a dry run). Every row is read and checked with the respondent rules; nothing is
   stored. The result lists up to 200 problems as row, column and a code (never a value) and the
   exact totals per code.
4. **Import.** The importer confirms they may store the data (`confirmedLawfulBasis`), the job
   checks every row again and stores them. All or nothing: one failing row stores nothing, unless
   the importer chose "skip invalid rows"; a failure half way (a database error, the form's response
   limit, a worker that died) deletes what was stored.
5. **Result.** Counts, the problems, and the undo.

## Values

| Question | Cell |
|---|---|
| text, email, link, phone | the text |
| number, rating | `12`, `12.5`, `12,5` (a decimal comma); no thousands separators |
| date, day | `YYYY-MM-DD`, also `DD-MM-YYYY`, `DD/MM/YYYY`, `DD.MM.YYYY` |
| time | `HH:MM` |
| currency | `EUR 12.50`; a bare amount only when the question allows one currency |
| date range | `YYYY-MM-DD/YYYY-MM-DD` (either side may be empty) |
| tags | joined with `;` |
| yes/no | `Yes` / `No` (also `true`/`false`, `ja`/`nee`) |
| choice | the option's label (case and spacing ignored), `Item N` for an option with no label, or its id; several joined with `;` (a label may contain `;`); a text that is no option is the "other" answer when the question allows it |
| address | the export's one line, `street number addition, postcode city` and the country code unless `NL`, read back best effort |
| signature | the typed name; `[drawn signature]` cannot be imported |
| repeating group (columns layout) | one column per item and question |
| hidden field | the text, for declared names |
| staff-only question | as its type, imported as the form's internal answers |

An empty cell is no answer (Required decides). The export's formula guard (a leading `'` before
`=`, `+`, `-`, `@`, a tab or a carriage return) is taken off. Nothing in a file is evaluated.

## What an imported response is

* The same stored response as a submission: `answers`, `hidden_fields` and the internal answers
  go through the same encryption; `form_version` is the published version; the ending and the
  calculated values are the server's; the form's retention is applied from the submission time (a
  row already past it is refused, not stored and deleted at once).
* **Anonymous**: no responder, no account. A responder or email column is never turned into one.
* **Marked** `csvImportId` (the id of the import job), shown to staff as an "Imported" badge in the
  list and on the response; set by the server only (a submission body cannot claim it). The importer
  is read from the import's record, so deleting an account pseudonymises one place.
* **`submitted_at`**: the file's "Submitted at" column when mapped (ISO 8601, `YYYY-MM-DD HH:MM[:SS]`,
  `DD-MM-YYYY`; no zone means UTC; a future time or one before 1990 is refused), else the import time.
* **Nothing fires**: no actions, webhooks, email actions, registration deliveries or notifications,
  no AI-insight notice (so AI insights never analyse an imported response).
* The form's response limit applies like a submission's (the same locked insert). A closed form
  accepts an import. Only forms collected here that were published once.

## Same rules as a respondent

`services/response_import/validation.py` `check_submission(published, draft, answers,
hidden_values, form_id=...)` runs, in the submission path's own order, `validate_group_answers`,
`drop_hidden_group_answers`, `drop_draft_calculations`, `calculate_and_check` (field rules,
calculated values, Required, types, answer rules, choice logic, option sources; with `enforce=True`,
so `RESPONSE_VALIDATION_ENFORCE` never softens an import), `reached_ending_id` and the date
rules, and returns the problems instead of raising. `tests/app/response_import/test_parity.py` runs one
fixture set through the respondent submission and through it and requires the same verdict.
The submissions API can call the same function; `submit_response` calling it too is a follow-up.

## Routes

All under `/workspaces/{workspace_id}/forms/{form_id}/imports`, all needing `response.import`
and `CSV_IMPORT_ENABLED` (else 404). Answers are `Cache-Control: no-store`.

| Route | What it does |
|---|---|
| `POST /` | The file as the body. 201 with the import: `headers`, the form's `targets`, the suggested `mapping` and `notes`. |
| `GET /` | The form's imports, newest first. |
| `GET /{id}` | One import; `targets` while its file waits. |
| `POST /{id}/check` | `{mapping, skipInvalidRows}`: queue a dry run (202). |
| `POST /{id}/run` | `{mapping, skipInvalidRows, confirmedLawfulBasis}`: queue the import (202). |
| `POST /{id}/rollback` | Delete what a completed import created, within 14 days of its end. |
| `DELETE /{id}` | Discard an upload that is not being processed; its file is deleted. |

Errors carry a `code`: `unsupported_format` (415), `too_large`, `too_many_rows` (413),
`too_many_columns`, `cell_too_long`, `header_too_long`, `empty_file`, `no_header`, `no_rows`,
`unreadable_encoding`, `unreadable_file` (422), `rate_limited` (429, `Retry-After`),
`import_in_progress` (409), `workspace_busy` (429), `not_ready` (409), `needs_confirmation`,
`no_mapping`, `duplicate_target`, `unknown_target`, `unknown_column`, `target_not_importable` (422),
`form_not_published`, `form_not_importable` (409), `not_rollbackable`, `rollback_expired` (409).

## The file and the audit entry

The upload waits **encrypted** in `response_import_files` (the responses' keyset; the context
names the import, and the key is bound to the workspace and the form), never on disk, never in a
job argument or a log line. It is deleted when the job ends in any outcome, when the importer
discards it, with the form or the workspace, and at the latest an hour after it was uploaded (the
hourly `response_import_sweep`, which runs whether or not the switch is on). The job's only argument is
the import id.

One `response_imports` row per import is the audit entry and the job state: who (`deleted-user`
after an account is deleted), the form, the counts, the status and outcome code, the mapping as
column positions and target keys, the options, the file size, encoding and separator, the problems
as `{row, column, field, code}`, who undid it and when. Never a value, a file name or a question
title; the file's headings are kept only while its file is.

## Limits and jobs

10 uploads per user and form per hour; one import being checked, queued or run per form (a partial
unique index); at most 2 per workspace. The job runs on the `exports` queue (served by the
backend's jobs worker, so no `JOBS_QUEUES` change). It reads and stores 100 rows at a time, beats
(`heartbeat_at`) at least every 20 seconds, and owns the import only while its claim is current. The
sweep queues an import no worker took after 2 minutes, fails one that waited an hour
(`queue_timeout`) and one whose worker died three times (`worker_lost`), undoing what it stored. All
limits are constants in `services/response_import/limits.py`.

## Not in 4.3

XLSX, a ZIP with a group's table, mapping a column to a respondent identity, opt-in side effects
for imported responses, skipping rows whose response id already exists.
