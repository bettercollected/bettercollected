# Reports on a form's answers

Counts, averages, distributions and over-time series computed on request from a form's
stored answers. This page describes the server part (the query API) and, at the end, the
page that shows it. It is behind the
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

A question is one entry across the form's versions, by its id, for as long as the newest version
that has it still makes it reportable: a version that makes it internal, or of a kind a report
does not use, takes it back. The newest version that has
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
  server computes two passes over answers at once (`429` `report_busy`). Passes in flight in all
  replicas together are counted too (six, in a counter of the shared rate limiter that a pass
  gives back when it ends and that a crashed process loses with its 60 s window), so the
  limit holds across replicas, closely rather than exactly.
* A pass has a time budget of 30 s (a 20,000-response one takes about 2.5 s): past it the
  pass is cancelled, its places are given back and the query answers `503` with the code
  `report_timeout`.
* A stored number too large or strange to add up (an average that cannot be rounded to two
  places, or a magnitude beyond 40 digits) is left out of that value, which is `null`, and the
  result carries the notice `unreadable_answers`; it is never a server error.

### Saved views

A view is a **name**, a **scope** and a report **definition** (the body of `POST /query`),
stored in `form_report_views` (revision 0040, Postgres only, not imported from Mongo). All
five routes sit under `.../forms/{form_id}/report/views`, answer `Cache-Control: no-store`, are
gated like a query (`response.read` and `analytics.read` on the form) and answer `422
reporting_off` before anything else while the switch is off.

| Route | What |
|---|---|
| `GET /views` | the views the caller may open (the form's own and their private ones), each with its definition, `mine`, `ownerName` (null for their own, and for a maker who is no longer a member), `revision`, `canEdit` and `canDelete`; `canShare` and the limits |
| `POST /views` | `{name, scope?: "private" \| "form", definition}`, 201 |
| `GET /views/{view_id}` | one view; 404 `view_not_found` for a missing one and for another person's private one |
| `PATCH /views/{view_id}` | `{revision, name?, scope?, definition?}`; 409 `view_changed` when `revision` is not the current one |
| `DELETE /views/{view_id}` | 204 |

* **Private** (the default): the owner's notebook. Another member's private view is a 404 to
  everyone, an owner or admin of the workspace included. At most 20 per person and form.
* **Form** (`scope: "form"`): visible to everyone who may open the report. Creating one, changing
  one (any editor of the form: it is the form's) and deleting your own needs `form.edit`; deleting
  one made by someone else needs `members.manage` (an owner or admin: moderation); only its maker
  makes it private again. At most 50 per form. There is no public link and no minimum group size.
* **What is stored** is the definition as a query would accept it for this caller (`422` with the
  query's codes otherwise, plus `invalid_view` for the request itself): question and option ids,
  enums, numbers and dates, never an answer, an identity or text a respondent wrote. A view is
  validated again every time it runs, because the page posts its definition to `/query`: a form
  change that makes a card invalid shows on the card. The name is text the staff member typed;
  it is shown, and never logged or audited. A name is used once per scope (and owner, for a
  private view), `409 view_name_taken`; the limits answer `409 view_limit`.
* **Audit** (docs/audit-log.md): what the whole form shares is written before it is done, ids and
  enums only: a form view created, changed or deleted (by anyone), a view shared or made
  private again. A private view's creation, change and deletion are not.
* **Clean-up.** While the switch is on, deleting a form deletes its views and removing a member
  deletes their private views (the views they made for the form stay, as a former member's).
  While it is off nothing reads or writes the table, so the views of a form or a member deleted
  in that time stay in it, unreachable.

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

## The Report page

Under **Responses > Report** in the form's side menu (**Rapport** in Dutch), and as a
**Report** button in the responses toolbar that carries the list's filters (date range,
deletion-request status, anonymous or identified, form version; never the page, the sort or the
search). It is there only while `reportingEnabled` is true in the permissions answer and the
member holds `response.read` and `analytics.read`; otherwise the address shows "Reports are not
turned on yet" and asks the server for nothing.

* **The report lives in the address.** The filters use the list's own parameters (`from`, `to`,
  `status`, `who`, `version`); once the cards are changed they are written as `cards`
  (base64url JSON of question keys, built-in names and enums, never an answer or a name). Without
  `cards` the page shows the **Overview**, computed from the form's questions and never stored:
  the response count, responses over time, then one card per reportable question in form order
  (the first twelve, with "Show all"). A malformed address falls back to the Overview.
* **Cards** can be added, changed (group by, show, per day/week/month/year, as), moved and removed;
  one request asks the server for all of them.
* **Views.** A bar above the filters opens a saved view (the Overview, my views, the form's own),
  saves the report on screen as one (for the member alone, or for everyone who can open the
  report when they may edit the form), and updates, renames, shares or deletes the open one. The
  address keeps the working report; `view=<id>` says which saved view it started from, so the
  page can say "Changed since it was saved" and offer Update. A view the member cannot open
  (deleted, or someone else's private one) is said so and the Overview shows.
* **Charts** are hand-written SVG (no chart library): a number tile, a bar chart, a donut (six slices
  at most, otherwise a bar), a line over time (columns for 14 points or fewer) and a table. Every
  chart prints its values, a donut's slices also differ by a pattern and its legend names each with
  its value, and every card has a "Show as table" switch. A chart is one image with a sentence that
  describes it, the figures are in a table that follows it, and no mark is a tab stop.
* **Refusals** are explained on the page: `too_many_rows` (offers the last 30 days or the current
  version), `rate_limited` and `report_busy` (retry), `report_timeout`, the notice
  `unreadable_answers`, a card whose question the form no longer has (offers removing it), and a
  form without responses.
