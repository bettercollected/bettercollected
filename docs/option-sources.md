# Options from a list or from another form's answers

A dropdown or a multiple choice question can take its options from a **workspace list** (reference data the
workspace maintains: municipalities, products, branches) or from **the answers given to one question of another
form** of the same workspace (for example the participants who registered), instead of options typed into the
question. Everything happens on the server: no URL is fetched, nothing comes from the browser, and a respondent's
form only ever receives the labels of the options.

| Setting | Off (default) | On |
|---|---|---|
| `OPTION_SOURCES_ENABLED` | A save that adds or changes a question's source is refused (422 `option_sources_disabled`), and no list can be created. Sources already stored keep working: they are served, validated and exported, and lists can still be edited and deleted. | Creators can add lists and point questions at them. |

It is a server setting like the other feature switches (`docs/settings-inventory.md`): a change reaches the backend
when it restarts. The workspace permissions answer carries it as `optionSourcesEnabled`; the webapp shows the lists
page and the source picker from it.

## Workspace lists

A list has a name (unique in the workspace), an order (as stored, or alphabetical) and items. An item is a label and
an optional **group**: the key that a dependent list is filtered by (the cities of a country: the group of
Amsterdam is "Netherlands"). The group is never shown to respondents.

- Limits: 100 lists per workspace, 2,000 items per list, a label of at most 200 characters, a name of at most 100.
  Text is stored in Unicode form C, trimmed, without control or invisible characters; a label and group pair is
  there once (compared ignoring case and spacing).
- Each item has an id the server made (`li…`). It stays through renames, re-ordering and CSV re-imports, so answers
  and forms that name it keep working. Whoever changes a list sends the revision they read; another save in
  between is a 409 (`list_changed`) and nothing is overwritten.
- **Who**: reading a list needs `form.read`, creating, changing, importing and deleting one needs `form.edit`.
  A list is always looked up through the workspace in the URL: another workspace's list is a 404.
- **CSV**: `label,group,id` (the group and the id are optional), UTF-8, at most 1 MB and 2,000 rows. An import
  replaces the items; a row with an id of the list keeps it, a row without one that matches an existing item (same
  label and group) keeps that item's id. An export never starts a cell with `=`, `+`, `-` or `@` (an apostrophe is
  put in front, and an import takes it off again).
- A list a form still uses cannot be deleted (409 `list_in_use`, naming the forms). Answers already given keep the
  label they were given with.

API: `GET/POST /workspaces/{id}/option-lists`, `GET/PATCH/DELETE .../{list_id}`, `POST .../{list_id}/import`,
`GET .../{list_id}/export`.

## Another form's answers

Another form's answers are used only when the **source question opted in**. On the question of the form that collects
the answers there is a setting, "Answers may be shown as choices in other forms of this workspace" (`shareAsChoices`),
off by default. While it is on, the people who fill in that form are told next to the question ("Your answer may be
shown as a choice in other forms of this organisation") and the form's privacy panel says so too. Only answers given
**while the page the respondent filled in showed that notice** are ever offered: answers given before the setting,
answers given on a version without it, and every answer once the setting is turned off are never used. The form a
respondent loads carries a signed token (`shareNoticeToken`, valid 24 hours, bound to the workspace and the form) that
names the questions whose notice that page showed; the page sends it back with the submission (`share_notice_token`).
The server stamps the response with the questions of the token that the form's current version still shares: no token,
a forged, expired or foreign one, a form published after the page was loaded, or a client that never showed the notice
stamps nothing. A client cannot set the stamp in any other way (the body, a provider import and a respondent edit
never do), and a copy of a form (template, duplicate) starts with sharing off. The server checks the stamp
for every answer it offers, and refuses to save a question that points at a question that does not share (422
`option_source_not_shared`). Turning the setting off in the builder stops all use at once; turning it on again brings
back only the answers that were given while it was on.

A creator who points a question at another form's answers also needs `response.read` on **that** form (checked when the
source is added or changed; a form that already has one is not asked again, so others can keep editing it). The
question must be a short text, dropdown or multiple choice question of another form in the same workspace: never an
email, phone, number, address or file question, never an internal question, and never one whose options come from a
source themselves. An API key never sets such a source (it is set in the builder).

**The people who open the form see these answers as choices, without being told who gave them.** Use it only for
answers those people agreed to share, such as a participant list. The builder says so and asks for confirmation.

- Which answers count: those of responses that have answers to a question that shared them (above), in this workspace,
  with **no deletion request of any status** (a respondent who asked to be erased is not shown), not submitted with the
  anonymous choice, not past their retention, and not hidden by logic (a stored answer to a question the respondent was
  not asked is left out).
- What is offered: the text of each answer (the labels of the chosen options, for a dropdown or multiple choice),
  once per distinct text (compared ignoring case and spacing; the first spelling is shown), alphabetically, at most
  1,000 of them and from at most 10,000 responses. A form says when the options were cut.
- What a respondent receives: `{id, label}` and nothing else. The id of an option is a keyed hash of its normalised
  label (scoped to the workspace, the form and the question): it is the same every time, and a log, a URL or an event
  that holds one reveals no label. The form a respondent loads does not name the other form or its question, and the
  page says under the question that "the choices come from answers other people gave to another form of this
  organisation".
- Freshness: the server rebuilds the options whenever the eligible responses or the source question change (an edited,
  deleted, expired or deletion-requested response, a retyped or renamed question, the setting turned off), in every
  process, at once. A source that only gained responses is served as it was for at most 5 seconds by the respondent
  endpoint (never by a submission, which checks against the current set), so a burst of sign-ups does not rebuild it
  for every request. There is no other timer. The options are kept in memory only and never stored: at most 256
  sources and 200,000 options in all, at most two rebuilds at a time per process, and one response that cannot be read
  is skipped, not a failure.
- **Erasure.** When a response of the source form is erased (a completed deletion request, a staff delete,
  retention, an account or form deletion: every way a response goes), its label leaves the options at once. The choices
  other people made from it are redacted too: once **no eligible response still offers** that option, the label
  snapshot beside the chosen id becomes `[removed]` in every consuming response of the workspace (all forms that use
  that source question), so exports, screens, insights and webhooks or emails sent from then on show `[removed]`.
  The erasure notes which options the erased responses offered (option ids only, never text) in the same
  transaction; a background run starts right after and the jobs worker repeats it every two minutes, so a crash only
  delays it. A note is **kept for 15 minutes** and worked on every pass until then, so a submission that took the
  option while the erased response still offered it, and committed a moment after the first pass, is redacted by the
  next one. Erasing one of two responses that gave the same answer changes nothing.
  What cannot be undone or is not reached: webhooks and emails already sent, exports already downloaded, a
  respondent's own saved draft, and the consuming form's stored export files (kept 24 hours, then deleted) keep what
  they held. Past the caps (a source's responses read for its options, the consuming forms looked up) an option is
  judged by what could be read, so a choice can be redacted although a response beyond the cap still offers it
  (redacting too much, never too little). The ids in a note are the option's id under every member of the signing key
  ring, so a key rotation does not stop it matching (see [auth-key-rotation.md](auth-key-rotation.md)). The source form's notice tells its respondents that a choice someone else made from their
  answer may stay in that person's response until their own answer is erased.
- **Switch off.** With `OPTION_SOURCES_ENABLED` off, another form's answers stop being offered at once: the
  respondent endpoint answers `available: false` with no options, a submission with a new choice from them is refused
  (`option_unavailable`) and the builder preview is empty. Workspace lists keep working. A choice already stored keeps
  its label, and the erasure redaction still runs.
- AI insights never receive another form's answers: a choice that came from them is sent to the model as "[choice
  from another form]" (a workspace list's label is reference data and is sent).
- Anonymous submissions: a respondent who chose to submit anonymously is left out, because a name in a public list
  would defeat that choice. Respondents who are simply not signed in count.

## What a respondent submits

The answer holds the chosen option id and a label snapshot the server writes beside it (`choice.label`,
`choices.labels`), so it stays readable when the item is renamed, removed or the other response is deleted. A client
cannot set the snapshot: it is replaced on every submission, and removed from questions that have options of their
own. Exports, webhooks, email actions, the Google Sheets action and the screens show the label, never the id.

On submission, and when a respondent changes a choice in an edit, the server checks that every chosen option is
offered **now** (and, for a dependent list, that it fits the parent's answer). A removed option is refused (422
`invalid_answers`, rule `option_unavailable`, with the question id) and nothing is stored. An edit that leaves a
choice as it was does not check it again. A question the respondent does not see (hidden by logic) is kept as sent,
as for every hidden answer.

`GET /workspaces/{id}/forms/{form_id}/options/{field_id}` serves the options (`q`, `limit` up to 100, `offset`,
`parent` for a dependent list): public like the form, labels only, never cached. It answers only for a form a
respondent may fill in **right now**, judged at every call as the submit does: not hidden, open (not before its open
date, not from its close date), not full, a signed-in respondent where the form asks for a verified identity, and for
a private form a signed-in member of one of its responder groups (read only for such a form; one user's access never
serves another). Unknown, unpublished, closed, hidden, full, unauthorised and unsourced all answer the same 404.
It is limited from memory per client before any query (four times the per-client limit per process), then 120
requests a minute per client and form and 3,000 per form (429 with `Retry-After`). Behind a reverse proxy set
`TRUSTED_PROXIES` first: the limits count client addresses, and without it every respondent shares one.

## Limits of this version

- Option show/hide logic and option filters do not apply to a question with a source; a dependent list uses its
  items' groups instead. A condition on such a question can only test whether it is answered.
- Not inside a repeating group; not in templates (a copy of a template or of a form to another workspace loses its
  sources, a duplicate keeps a list source and loses another form's answers).
- The edit operations of the AI chat and MCP do not set a source (the builder and the form spec API do, for lists;
  another form's answers only the builder).
- Replacing the items of a list (a save of the items or a CSV import) must name the revision that was read
  (`expectedRevision`; 422 `revision_required` without it, 409 `list_changed` when it is stale).
- No per-change history of a list: the last editor and revision are kept, and every change is logged with ids and
  counts only.
