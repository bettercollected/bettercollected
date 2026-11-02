# Audit log: reading the workspace's activity

The workspace audit log (`workspace_audit_events`) records who did what to a
workspace: access and team changes, members, forms, responses read or deleted,
exports, API keys, single sign-on break-glass use. This page covers the two
routes that read it, behind `AUDIT_LOG_UI_ENABLED`. The writers are not part of
that switch: events are recorded whether or not anyone can read them yet.

## Switch

`AUDIT_LOG_UI_ENABLED` (default off). While it is off both routes answer 422
`audit_log_off` before anything is read, and `GET /workspaces/{id}/permissions`
says `auditLogUiEnabled: false`, so the dashboard shows no Activity page.

## Routes

Both are read only and need `audit.read` (Owner, Admin and Privacy officer).

| Route | Notes |
|---|---|
| `GET /workspaces/{workspace_id}/audit-log` | the workspace's entries |
| `GET /workspaces/{workspace_id}/forms/{form_id}/audit-log` | the entries about one form; 404 for a form that is not this workspace's |

Entries come newest first, a page at a time (`limit` 20 by default, at most
100). The reply has `nextCursor`; send it back as `cursor` for the next, older
page. There is no offset and no total.

Filters, all applied on the server: `area` and `event` (repeatable; the kinds
of the catalogue), `actor` (who did it), `target` (who it was done to),
`involving` (either of the two), `form_id` (workspace route only), `from` and
`to` (ISO date-times, both ends inclusive). An area or kind the log does not
list, an id that is not an id, or a range that ends before it starts is 422
`invalid_filter`; an unreadable cursor is 422 `invalid_cursor`.

Areas: `access` (grants, a form's access mode, teams), `members`, `forms`,
`responses` (previous answers read, answers edited, responses deleted, exports),
`api_keys`, `security` (single sign-on break-glass use, the authenticator-app
rule, and changes to the workspace's security settings: single sign-on
connections and the require-single-sign-on switch and default role, verified
email domains, directory sync tokens and group roles, the AI consent, the custom
domain) and `integrations` (email actions and case-system services and
registrations: created, changed, switched on or off, deleted).

Under `forms` too: `form_copied_out` (a form's structure was copied to
another workspace or downloaded as a file) and `form_promoted` (a form was copied
here from another workspace), behind `FORM_PROMOTION_ENABLED`; each holds the
form's id and, in the workspace's own records, the other side's ids and a count
of what was adjusted, never a title (docs/environments.md).

Settings and integration entries carry ids and enum values only: the kind of
connection or directory (`connectionType`, `directoryType`), an on/off setting's
new value (`required`, `enabled`), the AI provider's id (`provider`), the roles
before and after (`role`, `previousRole`) and, for an integration, `changed`:
which parts changed, from a fixed list (for example `team_recipients`,
`base_url`, `secret`), never their content. No hostname, URL, address, template,
name, token or secret is stored.

Which changes refuse when the entry cannot be stored (503 `audit_unavailable`,
nothing changed) and which do not follows one rule: a change that opens access,
sends answers somewhere new or removes configuration is recorded first and
refused; a change that closes a way in, or that touches something switched off,
is recorded best effort after the change.

- Email actions and a form's case-system registration follow the same rule: one
  that is on, or being switched on, is recorded first; one that is switched off,
  or being switched off, is best effort. A case-system service shared by forms is
  recorded first when it is changed (its address or secret decides where their
  answers go) and best effort when it is created or deleted (an unused one).
- Directory sync: creating the directory and deleting it are recorded first. A
  delete lifts the directory's own deactivations, so members are enabled again.
  Rotating the token is best effort and written after the change: it is the only
  way to stop a leaked token and the audit store must never stand in its way.
- Turning "Require single sign-on" off is recorded first. It widens sign-in
  again, so recovering from a lockout through the product depends on the audit
  store being up; the owner's email-code break-glass and an operator with
  database access do not.
- A verified email domain is recorded once the verification has stood (never
  for a claim another workspace won); when the entry cannot be written the
  verification is taken back and the request is refused.
- Enabling a single sign-on connection disables the others: each gets its own
  `sso_connection_disabled` entry.

## What an entry holds

Codes, ids and enum values. The dashboard words each entry in the reader's
language from `event` and the fields; the server returns no sentence. There is
no answer, no email address, no name typed into a form and no free text in an
entry.

- A `team_linked` entry says which team (`groupId`) and whether a directory group was linked to it or unlinked from it (`linked`), and carries our id of the directory group (`scimGroupId`); the directory's own name for the group is not stored. An unlink that the directory causes (it deletes a linked group, or the directory is removed) is written by the directory's own actor, not a member. The page reads the entry as "linked a directory group to the team" or "unlinked a directory group from the team".
- `responseId` is returned only to someone who may read that form's responses.
  A Privacy officer sees who read or changed which form's response history, and
  when, but gets no response id.
- `sessionId` is returned only to an Owner or an Admin.
- `labels` resolves the ids of the page, now, inside this workspace only:
  `members` (a current member by display name, never an address; anyone else is
  `former` with no name, shown as "a member who has left"; a member whose
  membership is disabled counts as `former` too), `forms` (current
  title, or `gone`) and `teams` (current name, or `gone`). A name that could
  not be looked up is empty and the page still loads.
- `retentionDays` is how long entries are kept; the page states it.

## The dashboard pages

While the switch is on, whoever holds `audit.read` gets an **Activity** item in
the sidebar (`/dashboard/activity`) and an **Activity** item in each form's side
menu, after Versions (`/dashboard/forms/{id}/activity`: the same list with the
form fixed). With the switch off there is no item, the routes redirect to the
forms list and the dashboard makes no request.

Each entry is one sentence in the reader's language, built in the browser from
the codes and labels; an event kind the dashboard does not know reads "An action
was recorded." The filters (type, person, form, from and to in UTC) are kept in
the address. By default the break-glass requests (one entry per request of an
owner's email-code session) are left out of the list; choosing the Security
type shows them. The page states how long entries are kept.

## Who sees what

A Privacy officer holds `audit.read` and never an answer permission, so the
feed of a restricted form (who was granted what, who read its response
history) is open to them without a link into the responses. A Privacy officer
can read a restricted form's activity (ids only), while the webhook and email
delivery logs of that form stay withheld from them. A member who may
edit a form through a grant (a grantee Editor) does not see that form's
activity: the log is for the roles that hold `audit.read`.

Reading the log is not itself recorded; exporting it is (below).

## Export

`GET /workspaces/{workspace_id}/audit-log/export` and
`GET /workspaces/{workspace_id}/forms/{form_id}/audit-log/export` take the log out
as a file: `format=csv` (the default) or `format=json`, with the same filters, the
same permission (`audit.read`) and the same 404 for another workspace's form as the
list; both answer 422 `audit_log_off` while the switch is off. The Activity page's
**Export** menu asks for the file of the filters on screen.

- **Recorded first.** An export is the one read of the log that is recorded: an
  `audit_log_exported` entry (area Security) holds the format, the number of
  entries, the names of the filters used (never their values) and, for a form's
  export, the form's id. It is stored before the first byte is sent, and when it
  cannot be stored the export is refused (503 `audit_unavailable`) and nothing is
  sent. A refused export (not allowed, an invalid filter, too many entries, over
  the budget) records nothing. The file holds what existed when it was asked for,
  so it does not include its own entry.
- **As bare as the screen.** Each row is built from the list's own entry
  (field by field), never from the stored one, so a Privacy officer's file has no
  session id and no response id, exactly as their screen. Beside the ids it has the
  current names the list resolves (a member's display name, a form's title, a
  team's name; empty for anyone or anything gone), never an address. CSV cells
  that start with `=`, `+`, `-` or `@` are prefixed so a spreadsheet never runs
  them, and the file starts with a byte order mark so a spreadsheet reads UTF-8.
- **Bounded.** At most 100 000 entries (413 `too_many_rows`: narrow the filters, for
  example with a date range), and five exports per person and workspace in ten
  minutes (429 `rate_limited`, with `Retry-After`; a refused request does not use
  the budget). The file is streamed in batches of 500 and never built in memory.
- **Columns.** CSV columns are the list's fields in snake case (`id`, `event`,
  `area`, `at` in UTC, `actor_id`, ...) then `actor_name`, `target_name`,
  `to_name`, `form_title`, `team_name`; JSON has the same fields in camel case in
  an `entries` array beside `exportedAt`.

## Indexes

Revision 0038 adds the generated columns `form_id`, `user_id` and
`target_user_id` to `workspace_audit_events` and four indexes behind the
filters: `(workspace_id, created_at, id)` for the page, and one each for a form,
an actor and a target. The table is Postgres only and is not imported from
Mongo.
