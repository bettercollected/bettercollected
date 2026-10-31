# Email actions

A form's owners and admins can send an email when a response is submitted: to the form's team, and, if they choose, a copy to the person who answered. Off by default
(`EMAIL_ACTIONS_ENABLED`). Email actions contain no creator code: they run in the backend's jobs worker, on their own queue, never in the actions executor.

## Switch and mail server

`EMAIL_ACTIONS_ENABLED` (`true` / `false`, default `false`; [settings inventory](settings-inventory.md)). While it is off:

- creating an email action, switching one on and sending a test mail answer **422** `email_actions_off`;
- no submission queues a mail, the jobs send nothing (a mail waiting for a retry is parked and queued again when the switch is turned on), and the respondent's
  privacy panel names no recipient;
- everything else still answers: the list, edits that do not switch one on, switching one off, deleting and the log. Saved actions and the log stay as they are.

Mail goes through the instance's own mail server, the `MAIL_*` settings the auth service uses (`MAIL_SMTP_SERVER`, `MAIL_SMTP_PORT`, `MAIL_SENDER`, `MAIL_USER`,
`MAIL_PASSWORD`, `MAIL_STARTTLS`, `MAIL_SSL_TLS`, `MAIL_USE_CREDENTIALS`, `MAIL_VALIDATE_CERTS`); the From name is `ORGANIZATION_NAME`, never a workspace's. There is no
per-workspace mail server. Without `MAIL_SMTP_SERVER` and `MAIL_SENDER` an action cannot be switched on (422 `mail_not_configured`) and a queued mail fails with that
code. The jobs worker must serve the `emails` queue (below).

## What an email action is

One action belongs to one form (at most 5 per form). It has:

| Part | Rule |
|---|---|
| Name | Up to 80 characters, one line. |
| Team addresses | Up to 5, one plain address each (trimmed, case-folded; plus tags and dots are kept, so a tagged address counts only if it matches a member's exactly). **Each must be the address of a current, enabled member of the workspace**: checked when saved (422 `recipient_not_allowed`) and again every time a mail is sent, so a removed member stops receiving mail. Same rule as the "send me a copy" action. |
| Respondent copy | An `email` question of the form. Its answer in *this* submission receives a copy. See "The respondent's copy". |
| Questions | The questions the text may name, each with a name (`^[A-Za-z_][A-Za-z0-9_]{0,63}$`, unique, never `form_title`, `submitted_at` or `answers`). Same variables as webhooks; files are never sent; a repeating group is a list. |
| Templates | A subject and a message in **English and Dutch**, both required. The form's language (`nl`, `nl-BE`, ... is Dutch, anything else English) picks which one the team gets. |
| Condition | Optional: it runs only when a condition on the answers holds (see "Conditions"). |
| On or off | A switched-off action mails nothing. |

Permissions: configuring, the question list, the preview and the test mail need `workspace.manage` (owners and admins), because answers leave the system. Reading the log
needs `form.edit` or `audit.read` (editors, admins, owners and the privacy officer, who never reads answers).

## Templates

Plain text only. No HTML is ever produced, so what a respondent typed is text and nothing else. A template uses `{{name}}` placeholders and no other syntax:

| Placeholder | Value |
|---|---|
| `{{name}}` | the answer to a mapped question (a list is joined with `, `; the items of a group are one per line; yes/no in the form's language) |
| `{{form_title}}` | the form's title, one line, up to 120 characters |
| `{{submitted_at}}` | `2026-10-31 09:00 UTC` |
| `{{answers}}` (message only) | one `Question: answer` line for every mapped question; the lines of a long answer are indented |

Rules, all enforced by `backend/backend/app/services/email_actions/templates.py`:

- A placeholder that is not mapped nor built in is refused when saved (422 `unknown_placeholder`), and so is a `{{` or `}}` that is not part of one (`invalid_placeholder`).
- Rendering is **one pass**: a value inserted is never read again, so an answer that contains `{{answers}}` stays the text it is.
- Every value: control characters, line and paragraph separators (U+2028, U+2029), NEL (U+0085), bidirectional overrides and isolates (U+202A-U+202E, U+2066-U+2069), zero
  width characters and unassigned code points are removed (a line break in the **subject** or a name becomes a space, in the message a line break); each value is capped (2,000
  characters in the message, 200 in the subject) and the message at 20,000.
- The **subject is always one line**. The standard library refuses a header value with a line break, so nothing that slipped past cleaning could add a header. Recipients are
  validated as one plain address (no whitespace, control or format character, none of `<>(),;:"\[]`), all in `To`; there is no `Cc`, `Bcc` or `Reply-To`. Messages carry
  `Auto-Submitted: auto-generated`.

The editor's **preview** (`POST .../email-actions/preview`) renders a template with made-up answers by the same code that renders the real mail.

## The respondent's copy

A respondent-supplied address is the one place the system mails someone nobody on the team chose, so it is the most restricted:

- The address comes only from the `email` question of this very submission, read from the stored (decrypted in memory) answers at send time, never from a request, a header or the
  queue. It receives a copy of **their own** submission and nothing else. There is no endpoint that mails an address a caller supplies.
- **Fixed wording** (English or Dutch, by the form's language), not a template the creator wrote: the form's title on one line, a line saying why they got it, the answers of the
  mapped questions (their own, each capped; a calculation kept from respondents is left out) and the time. The subject is fixed wording with no title.
- Rate limited, counted in keyed hashes that name no address: 3 per hour per address and form, 10 per hour per address (all forms), 600 per hour per form. Over a limit, the run is
  `cancelled` (`rate_limited`) and not retried.
- A submission without a usable address queues no copy.

## Conditions

Both email actions and webhooks take an optional condition: `{operator: AND|OR, conditions: [...]}` in the model the form's logic uses (`FieldLogicCondition`, the same comparisons;
at most 10). Saved only when each condition reads a question of the form's pages (not an internal one, not a file, not a question inside a repeating group: use the group with
`COUNT`, `ANY` or `ALL`); the question's type is written from the form. The server evaluates it **when the submission is queued, on the submitted answers** (calculated values the
server computed included), in memory. A condition that does not hold writes a `cancelled` log row (`condition_not_met`) and queues nothing; one that cannot be read (its question
was removed) never runs the action (`condition_invalid`). A condition cannot be used to learn about other submissions: it reads this submission only.

## The queue, retries and the log

- Job `deliver_email`, plus the sweep `emails_redefer` (every 5 minutes) and the daily `purge_email_logs`, on the queue **`emails`** of the Postgres job queue, in the backend's jobs worker
  (`python -m backend.jobs.worker`, which now consumes `default,webhooks,emails`; if you set `JOBS_QUEUES`, include `emails`; the worker logs a warning at start when email actions are
  on and it does not serve the queue). The job's only argument is the log row's id: the message is built when the job runs, from the decrypted answers, and never queued.
- 5 attempts with exponential backoff and jitter: about 1 minute, 4, 16 and 64 minutes (capped at 2 hours). `recipient_rejected`, `smtp_rejected`, `invalid_message` and
  `mail_not_configured` fail at once; connection, timeout, TLS, authentication and 4xx answers retry.
- The actions executor (which runs creator code) connects as `bc_jobs_exec`; its row-level security limits it to `run_action` rows of the `actions` queue, so it cannot see, change,
  cancel or queue an email job. `tests/app/jobs/test_executor_role.py` proves it.
- The log is the shared action log (`action_logs`, type `email`): one row per mail (the team's and the respondent's copy are two rows), with the ids (workspace, form, action, response),
  the channel (`team` or `respondent`), a status (`pending`, `in_progress`, `retrying`, `delivered`, `failed`, `cancelled`), the attempt count, timings and one of our codes
  (`recipient_rejected`, `smtp_rejected`, `smtp_busy`, `smtp_auth`, `smtp_unavailable`, `smtp_error`, `timeout`, `tls_error`, `invalid_message`, `mail_not_configured`,
  `answers_unreadable`, `recipient_not_allowed`, `no_address`, `rate_limited`, `disabled`, `condition_not_met`, `condition_invalid`, `internal_error`). **No address, hash or domain of
  one, subject or content.** Kept 30 days.
- Erasure: deleting a response deletes its log rows, a mail not yet sent is never sent (the job finds the submission gone and drops the row), and deleting a form or workspace deletes the actions and
  the log. Mail already sent is out of our hands: the privacy panel says so.

## Privacy panel

While the switch is on and a form has an enabled action, the respondent's privacy panel (English and Dutch) says that the answers are also emailed to the form's team and/or that they
get a copy at the address they enter, and that deleting a response here does not delete mail already sent. The published form carries `emailDestination: {"team": bool, "copy": bool}`,
derived from the stored actions (a conditional action counts: it may run), never from a request. When it cannot be read the form is not served (503 `form_unavailable`).

## Test mail

`POST .../email-actions/{id}/test` sends the action's mail with made-up answers to **the signed-in user's own address and nobody else** (`{"channel": "team" | "respondent"}`), in the request, and
logs the outcome. 5 per action and 20 per workspace per minute, 20 per user per hour (429 `rate_limited` with `Retry-After`).

## API (workspace staff, camelCase)

| | |
|---|---|
| `GET /workspaces/{ws}/email-actions/status` | `{"enabled": bool, "configured": bool}` (any member) |
| `GET /workspaces/{ws}/forms/{form}/email-actions` | the form's actions |
| `GET .../email-actions/variables` | the form's questions that can be mapped |
| `POST .../email-actions` | `{name, en:{subject,body}, nl:{...}, fields:[{source,key}], teamRecipients, respondentField, condition, enabled}` -> 201 |
| `PATCH .../email-actions/{id}` | any of those; `respondentField: null` / `condition: null` remove them |
| `DELETE .../email-actions/{id}` | 204 |
| `POST .../email-actions/preview` | `{language, subject, body, fields}` -> the rendered text with made-up answers |
| `POST .../email-actions/{id}/test` | a test mail to yourself; returns its log row |
| `GET .../email-actions/deliveries?status=&limit=&offset=` | the log |

Not (yet) on the public API or the MCP server.
