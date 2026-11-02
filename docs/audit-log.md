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

Settings and integration entries carry ids and enum values only: the kind of
connection or directory (`connectionType`, `directoryType`), an on/off setting's
new value (`required`, `enabled`), the AI provider's id (`provider`), the roles
before and after (`role`, `previousRole`) and, for an integration, `changed`:
which parts changed, from a fixed list (for example `team_recipients`,
`base_url`, `secret`), never their content. No hostname, URL, address, template,
name, token or secret is stored. Changes that open access, send answers somewhere
new or remove configuration are recorded before they are made and refused with
503 `audit_unavailable` when the entry cannot be stored; closing a way in and
creating something inert are best effort.

## What an entry holds

Codes, ids and enum values. The dashboard words each entry in the reader's
language from `event` and the fields; the server returns no sentence. There is
no answer, no email address, no name typed into a form and no free text in an
entry.

- `responseId` is returned only to someone who may read that form's responses.
  A Privacy officer sees who read or changed which form's response history, and
  when, but gets no response id.
- `sessionId` is returned only to an Owner or an Admin.
- `labels` resolves the ids of the page, now, inside this workspace only:
  `members` (a current member by display name, never an address; anyone else is
  `former` with no name, shown as "a member who has left"), `forms` (current
  title, or `gone`) and `teams` (current name, or `gone`). A name that could
  not be looked up is empty and the page still loads.
- `retentionDays` is how long entries are kept; the page states it.

## Who sees what

A Privacy officer holds `audit.read` and never an answer permission, so the
feed of a restricted form (who was granted what, who read its response
history) is open to them without a link into the responses. A member who may
edit a form through a grant (a grantee Editor) does not see that form's
activity: the log is for the roles that hold `audit.read`.

Reading the log is not itself recorded.

## Indexes

Revision 0038 adds the generated columns `form_id`, `user_id` and
`target_user_id` to `workspace_audit_events` and four indexes behind the
filters: `(workspace_id, created_at, id)` for the page, and one each for a form,
an actor and a target. The table is Postgres only and is not imported from
Mongo.
