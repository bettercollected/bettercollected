# Reports on a form's answers

Counts, averages, distributions and over-time series computed on request from a form's
stored answers. This page describes the server part (the query API). It is behind the
server setting `REPORTING_ENABLED` (`true` / `false`, default `false`, set in the
environment and not in the admin portal until it is released; see the
[settings inventory](settings-inventory.md)). While it is off, every route below answers
`422` with the code `reporting_off` before the session, a permission or any row is looked
at, and nothing else changes: the responses list, the export, analytics and AI insights
behave the same with the setting on or off. The permissions answer
(`GET /workspaces/{id}/permissions`) carries `reportingEnabled`.

## What a report is, and what it is not

* **No new copy of an answer.** Answers stay encrypted at rest. A query reads the form's
  responses in batches, decrypts each batch in memory, adds it up and drops it. What is
  kept, in this process only and only for a while, are the finished aggregates (counts and
  sums per group), never a row, an answer or an identity.
* **Aggregates only.** A result never holds a response id, an answer's text or a
  respondent's identity. A question's typed "Other" is counted as the group "Other"; its
  text is never read.
* **Counted as stored.** An answer to a question that logic hid, or that a page jump
  skipped, is stored and counts, as it does in the export. A report says "answered", never
  "saw".
* **Current values.** A staff edit changes the next report; a deleted or expired response
  is gone from the next one.

## Who may

`response.read` **and** `analytics.read`, both on the form. Owners, Admins, Editors,
Reviewers and Viewers hold both; a form-level grant carries both for its role. A **Privacy
officer** holds `analytics.read` but never `response.read`, so is refused: nothing derived
from answers is theirs to read. A restricted form answers `404`, the answer of a form that
does not exist, to a member it is closed to.

## Routes

Both under `/workspaces/{workspace_id}/forms/{form_id}/report`, every answer
`Cache-Control: no-store`. The query is a `POST` with the definition as its JSON body, so no
choice a report is about sits in a URL.

### `GET /fields`

What the caller may build a report from.

```json
{"fields": [{"key": "q:<question id>", "label": "...", "kind": "choice", "dimension": true,
             "measures": ["count"], "versions": [1, 2], "inCurrentVersion": true,
             "options": [{"id": "...", "label": "..."}]}],
 "builtins": [{"key": "submitted_at", "buckets": ["day","week","month","year"]},
              {"key": "form_version"}, {"key": "respondent"}, {"key": "ending"},
              {"key": "status"}, {"key": "feedback_status"}, {"key": "source"}],
 "limits": {"maxRows": 20000, "maxCards": 24, "maxMeasures": 5}}
```

Reportable questions, by kind:

| Kind | Questions | As a group | Aggregates |
|---|---|---|---|
| `choice` | dropdown, multiple choice (one answer) | one group per option | count |
| `choices` | multiple choice, dropdown (several) | a response counts in each option it chose | count |
| `yes_no` | yes/no | yes, no | count |
| `scale` | rating, linear rating, opinion scale | one group per value | count avg min max |
| `number` | number | no | count avg sum min max |
| `currency` | currency, one currency only | no | count avg sum min max |
| `calculated` | calculated yes/no or number | yes, no | count avg sum min max |
| `date` | date | day, week, month or year | count |

Never reportable, whatever else is true: text, email, phone, link, address, signature, file,
matrix, table, ranking, tags, time, date range, repeating groups, questions whose options
come from a source, and internal (staff-only) questions. Built-in groups come from columns
the response row holds in the clear: the submission time, the form version, anonymous or
identified (never who), the ending reached, the deletion-request status, the newest feedback
status and the source (form, API, CSV import).

A question is one entry across the form's versions, by its id. The newest version that has
an option names it, an option only an older version has keeps its old label, and an answer
naming an option no version has any more is counted as "Removed option".

### `POST /query`

```json
{"v": 1,
 "filters": {"submittedFrom": "2026-03-01T00:00:00Z", "submittedTo": "2026-04-01T00:00:00Z",
             "status": ["none"], "respondent": "known", "formVersion": [2]},
 "tz": "Europe/Amsterdam",
 "cards": [{"id": "dept", "kind": "bar", "dimension": {"field": "q:<id>"},
            "measures": [{"agg": "count"}, {"agg": "avg", "field": "q:<id>"}]}]}
```

* `filters` are the responses list's plaintext filters (no search, and none on an answer).
* `tz` (an IANA zone, default `UTC`) decides the day, week (starting Monday), month and year
  of a time group.
* A card has a `kind` (`tile`, `bar`, `donut`, `line`, `table`), at most one `dimension`
  (a question key or a built-in, with a `bucket` for a date) and one to five `measures`.
  A tile has no dimension; a line needs a time dimension; a donut a dimension of at most six
  groups. `status` and `feedback_status` can only be counted.
* At most 24 cards, 16 KB, and every key is checked: unknown keys, text questions, an
  aggregate a question does not allow and a question the caller may not use are refused with
  `422` and the code `invalid_definition`, `unknown_field`, `field_not_reportable` or
  `op_not_allowed`. A question the caller may not use is refused exactly as one that does
  not exist.

The answer:

```json
{"definitionHash": "...", "token": "...", "generatedAt": "...", "n": 212, "scanned": 212,
 "cards": [{"id": "dept", "n": 212, "answered": 198, "skipped": 14, "multiple": false,
            "groups": [{"key": "<option id>", "label": "Care", "n": 74,
                        "values": [74, 4.2], "valueN": [74, 70]}],
            "otherGroups": {"n": 0, "count": 0}, "truncated": false}],
 "notices": []}
```

`n` is the number of responses the filters select; `answered` and `skipped` say how many
of them gave a value for the card's dimension (or, without one, for its first aggregate);
`valueN` is how many answers each value is made from. An average over no answers is `null`,
averages are exact decimals rounded to two places, and a card with many groups keeps the
biggest hundred and sums the rest in `otherGroups`.

### Limits

* A query that reads answers is refused with `413` and the code `too_many_rows`
  (carrying `count` and `max`) when the filters select more than 20,000 responses: narrow the
  dates or versions. A report is never partly computed. Cards that read no answer (counts by
  day, version, ending, respondent kind, source and statuses) have no such limit.
* 30 queries per user and form per minute (`429` `rate_limited`, with `Retry-After`), and a
  server computes two passes over answers at once (`429` `report_busy`).

## How it runs

Cards on plaintext columns are counted in SQL: nothing is decrypted. All other cards of a
query share one pass: responses are read in keyset batches of 500 in order of submission,
served by the `(workspace, form, created_at)` index, decrypted on a worker thread and added
up. Aggregates of a pass are cached in the process against an exact token (the number of
matching responses and a hash of each one's id and last change) and the form's revision, so
a new, edited or deleted response, or a changed form, makes the next query read again.

## Field-level access

The set of questions a caller may use as a group, a value or a filter comes from one place,
`ReportFieldPolicy.visible_fields` (`backend/backend/app/services/reporting/policy.py`).
Today it allows every question a member who may read the responses can already read;
field-level access will replace its body.
