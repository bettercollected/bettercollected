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
             "filterOps": ["is", "is_not", "any_of", "is_empty", "is_not_empty"],
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

* `filters` are the responses list's plaintext filters (no search) and, in `where`, conditions on
  answers (below).
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

#### Conditions on answers (`filters.where`)

At most 10 conditions `{"field": "q:<id>", "op": "...", "value": ...}`, every one of which a
response must meet to count. Each is checked against the form's questions as the caller may use
them (a question they may not use is refused exactly as one that does not exist, `unknown_field`;
text, address, signature, file and the like are `field_not_reportable`; a built-in is not a
question: the list filters narrow by those) and its operator against the question's kind
(`filterOps` in `GET /fields`; `op_not_allowed`):

| Kind | Operators | Value |
|---|---|---|
| `choice` | `is`, `is_not`, `any_of` | an option id of the question (`any_of`: a list of them) |
| `choices` | `has_any`, `has_all` | a list of option ids of the question |
| `yes_no` | `is` | `true` or `false` |
| `scale`, `number`, `currency` | `=`, `!=`, `>`, `>=`, `<`, `<=`, `between` | a number (`between`: two, the lower first) |
| `calculated` | `is` (yes/no) and the number operators | `true` / `false`, or a number |
| `date` | `before`, `after`, `between` | `YYYY-MM-DD` (`between`: two, the earlier first) |
| every kind | `is_empty`, `is_not_empty` | none |

A value is an option id, a number, a boolean or a date, never text: the only string a condition
takes is an option id the question has, so no answer text can be filtered on or stored in a
view (`invalid_definition`, naming the path and never the value). A comparison only matches a
response that gave a value (`is_empty` finds the others); a typed "Other" is the group "Other"
and its text is never read. With conditions every card is computed in the pass (which responses
count depends on what they answered), `n` is the number of responses that met them, and the
20,000-response cap still counts the set the plaintext filters select. A card grouped by
`status` or `feedback_status` is counted in SQL, which never reads an answer, so with conditions
it is refused (`422 op_not_allowed`) instead of ignoring them; the page says so on the card and
when a save is refused for it. A saved view stores
them with the rest of the definition (`v` stays 1: `where` is an optional key); the page never puts them in an
address.

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

### `POST /responses`: the responses behind a group

```json
{"definition": {...}, "card": "dept", "group": "<option id>", "cursor": null, "size": 25}
```

The definition is validated as a query's is (the same field policy, conditions included), and
the set it reads is held to the same cap (`413 too_many_rows` with `count` and `max`, counted
from the plaintext filters before any answer is read); the card must have a dimension the pass reads (not the deletion-request or feedback status). The
answer is a page of `{id, submittedAt, formVersion, respondent}` (`id` is what the response's
own page is opened by; `respondent` is `anonymous` or `known`, never who) for the responses that
met the definition's filters and fell in the group, oldest first, with `cursor`, `scanned` and
`exhausted`. The pass is the report's (keyset on `(created_at, id)`, decrypt, test, drop) and
stops when the page is full or 20,000 responses were read: `exhausted: true` means the set has
ended; a short page with a cursor means the budget ended, and asking again from the cursor goes
on. `size` is at most 100. It counts against the 30 queries a minute and the process's two
passes (`report_busy`) and has the pass's time budget (`report_timeout`); it is gated like a
query and answers `422 reporting_off` first while the switch is off. The cursor holds no secret
and gives no access: every read stays scoped to the workspace and form of the request.

### `POST /export`: one card as a CSV

```json
{"definition": {...}, "card": "dept", "format": "csv"}
```

The table of one card, as the Report page shows it: one row per group (its label, `Responses`,
`Share of answered (%)` and one column for each measure that is not a plain count, such as
`Average of Score`), after a few `key,value` lines that say what the file is: the form's title,
the card, what it is grouped by, how many responses it covers and how many answered, the
filters in words (a condition on an answer is counted, never stated: a value asked about is an
answer), the time zone the days follow and when the figures were made. It is UTF-8 with a byte
order mark, like the responses export, and every cell goes through that export's CSV writer: text
a spreadsheet would run as a formula (a leading `=`, `+`, `-`, `@`, tab or carriage return) gets
an apostrophe in front. The words in the file are English; the groups' labels are the form's.

* **Who may.** `response.export` on the form as well as `response.read` and `analytics.read`
  (Owners, Admins and Editors; a Reviewer or Viewer only with an export grant; never a Privacy
  officer): the file is what leaves the screen, and a small group can single a person out.
  A restricted form is a `404` to a member it is closed to, as for a query.
* **Same figures as the screen.** Only the asked card is computed, by the same pass, cache and
  limits as a query (`413 too_many_rows`, `429 report_busy`, `503 report_timeout`), and it counts
  against the 30 queries a minute. Downloads have a limit of their own, 10 per user and form per
  hour (`429 rate_limited`); one that produced no file (a refused or failed query) gives its
  place back.
* **Audited, then handed out.** The entry (`report_exported`, in the Activity page's Responses
  area: the form, `csv`, the channel `report` and the number of groups written) is stored before
  the file is returned; when it cannot be stored the answer is `503 audit_unavailable` and there is
  no file. It never holds the card, its title, its filters or a figure (docs/audit-log.md). The
  responses export's own entry (`response_export`) stays for exports of responses, so the two stay
  countable apart.
* **Never stored.** The file is built in memory and returned with `Cache-Control: no-store`,
  `Pragma: no-cache` and `X-Content-Type-Options: nosniff`; nothing is kept on the server.
  While the switch is off the route answers `422 reporting_off` first, before a permission is
  looked at or a row is read.

### Limits

* A query that reads answers is refused with `413` and the code `too_many_rows`
  (carrying `count` and `max`) when the filters select more than 20,000 responses: narrow the
  dates or versions. A report is never partly computed. Cards that read no answer (counts by
  day, version, ending, respondent kind, source and statuses) have no such limit.
* 30 queries per user and form per minute (`429` `rate_limited`, with `Retry-After`), and a
  server computes two passes over answers at once (`429` `report_busy`). Passes in flight in all
  replicas together are counted too (six, in a counter of the shared rate limiter that a pass
  gives back when it ends and that a crashed process loses with its 60 s window), so the
  limit holds across replicas, closely rather than exactly. One workspace may hold at most two
  of those six at a time (a counter of its own in the same scope), so a workspace that runs many
  reports cannot take every place from the others; the drill-down takes the same places. The
  figures are constants in `services/reporting/limits.py`, not settings.
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
| `PATCH /views/{view_id}` | `{revision, name?, scope?, definition?}`; 409 `view_changed` when `revision` is not the current one; checked before the audit entry, so a stale request leaves none |
| `DELETE /views/{view_id}[?revision=n]` | 204; with `revision`, 409 `view_changed` when the view is no longer at it (checked before anything is audited or deleted) |

* **Private** (the default): the owner's notebook. Another member's private view is a 404 to
  everyone, an owner or admin of the workspace included. At most 20 per person and form.
* **Form** (`scope: "form"`): visible to everyone who may open the report. Creating one, changing
  one (any editor of the form: it is the form's) and deleting your own needs `form.edit`; deleting
  one made by someone else needs `members.manage` (an owner or admin: moderation); only its maker
  makes it private again. At most 50 per form. There is no public link and no minimum group size.
* **What is stored** is the definition as a query would accept it for this caller (`422` with the
  query's codes otherwise, plus `invalid_view` for the request itself): question and option ids,
  enums, numbers and dates, never an answer, an identity or text a respondent wrote. A card's
  `title` is a caption of one request, not part of a view: a stored definition with one is a
  `422 invalid_definition`. A view is
  validated again every time it runs, because the page posts its definition to `/query`: a form
  change that makes a card invalid shows on the card. The name is text the staff member typed;
  it is shown, and never logged or audited. A name is used once per scope (and owner, for a
  private view), `409 view_name_taken`; the limits answer `409 view_limit`.
* **Audit** (docs/audit-log.md): what the whole form shares is written before it is done, ids and
  enums only: a form view created, changed or deleted (by anyone), a view shared or made
  private again. A private view's creation, change and deletion are not.
* **Clean-up**, whatever the switch says (views made while it was on do not outlive what they
  belong to): deleting a form deletes its views; removing a member, or deleting an account,
  deletes their private views (the views they made for a form stay, as a former member's);
  deleting a workspace deletes every view of it, also on a form that stays because another
  workspace holds it. These deletes are the only statements on the table while the switch is
  off: no route, no read and no write otherwise.

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
* **Answer filters.** Under the list filters, "Add answer filter" takes a question, a condition its
  kind allows and a value that suits it (an option, a number, a yes/no, a date; never text); the ones in
  force are chips that can be removed. **They are never written into the address**: a number or a date
  asked about is an answer value (a birth year, a salary, an appointment), and an address reaches browser
  history, access logs and Referer headers. The page keeps them in memory, so Back, a reload and a copied
  link lose them; a saved view carries them server-side, and `view=<id>` restores them. Sharing a
  filtered report means sharing a view. A condition on a question the form no longer has is shown with its
  reason and left out of the request.
* **Open these responses.** In a card's table, each group has a button that lists the responses
  behind it under the cards, a page at a time (submission time, form version, anonymous or
  identified, each linking to the response's own page); a short page that says the search stopped
  before the end offers "Show more". A group the responses list can filter on by itself (a form
  version, anonymous or identified, a day, week, month or year) also links to that list with the same
  filter; a group of answers does not, because the list has no filter on an answer.
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
