# Form versions: list, compare, restore

Each time a changed form is published it becomes a new version; a response keeps the version it was given in.
The **Versions** tab of a form (staff with `form.read`) lists them, shows one read-only, compares two, and (with
`form.edit`) restores one into the draft. It is behind the server setting `FORM_REVISIONS_UI_ENABLED` (default off;
see `docs/settings-inventory.md`). While it is off the routes answer 422 `form_revisions_disabled` and the tab is not shown.

## What each part does

- **List** (`GET /workspaces/{id}/forms/{form_id}/versions`): newest first, with the time, who published it and which
  one is live. "Who" is the member's current name and role; a person who has left is "a former member", and a version
  published before this was recorded shows "not recorded". No id or address is sent, and no response counts.
- **Read-only view** (`/{workspace}/dashboard/forms/{form_id}/versions/{n}`): the version's pages and questions as an
  outline. Nothing can be answered or saved from it. Each response page links to the version the response was given in.
- **Compare** (`GET .../version-diff?from=<n|draft>&to=<n|draft>`): what changed, in plain language: questions added,
  removed, moved, renamed or retyped; required switched; options added, removed or renamed; rules, logic and
  calculations changed; form title, description, language, theme, hidden fields. The server returns coded entries
  and the dashboard words them in English or Dutch. The text of rules is not spelt out. Purpose, retention and the other
  settings of the form are **not part of a version** and are not compared.
- **Restore** (`POST .../versions/{n}/restore`, body `{expectedUpdatedAt, replaceDraft}`): the version's pages,
  questions, texts, theme, hidden fields, logo placement and language replace the **draft**. Nothing is published and no
  version is changed or deleted; publishing the draft makes a new version. Not restored: the logo and cover image files,
  the consent list, the button text, settings such as purpose and retention, webhooks, email actions. The draft is
  replaced only with the caller's say-so (`replaceDraft`) when it holds unpublished changes (409 `draft_has_changes`), and
  not when it moved on since the page loaded (409 `form_changed`). A version with rules, choice logic, new question types
  or layout containers is refused while the setting that allows them is off, as a builder save would be.
