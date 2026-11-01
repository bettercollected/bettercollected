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

A creator who points a question at another form's answers needs `response.read` on **that** form (checked when the
source is added or changed; a form that already has one is not asked again, so others can keep editing it). The
question must be a short text, dropdown or multiple choice question of another form in the same workspace: never an
email, phone, number, address or file question, never an internal question, and never one whose options come from a
source themselves. An API key never sets such a source (it is set in the builder).

**The people who open the form see these answers as choices, without being told who gave them.** Use it only for
answers those people agreed to share, such as a participant list. The builder says so and asks for confirmation.

- Which answers count: those of responses that have answers, in this workspace, with **no deletion request of any
  status** (a respondent who asked to be erased is not shown), not submitted with the anonymous choice, and not past
  their retention.
- What is offered: the text of each answer (the labels of the chosen options, for a dropdown or multiple choice),
  once per distinct text (compared ignoring case and spacing; the first spelling is shown), alphabetically, at most
  1,000 of them and from at most 10,000 responses. A form says when the options were cut.
- What a respondent receives: `{id, label}` and nothing else. The id of an option is a keyed hash of its normalised
  label (scoped to the workspace, the form and the question): it is the same every time, and a log, a URL or an event
  that holds one reveals no label. The form a respondent loads does not name the other form or its question, and the
  page says under the question that "the choices come from answers other people gave to another form of this
  organisation".
- Freshness: the server rebuilds the options whenever the eligible responses change (a new, edited, deleted, expired
  or deletion-requested response), in every process; there is no stale copy to wait out. The options are kept in
  memory only and never stored.
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
`parent` for a dependent list): public like the form, published forms only, labels only, never cached, 120 requests
a minute per client and form and 3,000 per form (429 beyond). Unknown, unpublished and unsourced questions all answer
the same 404.

## Limits of this version

- Option show/hide logic and option filters do not apply to a question with a source; a dependent list uses its
  items' groups instead. A condition on such a question can only test whether it is answered.
- Not inside a repeating group; not in templates (a copy of a template or of a form to another workspace loses its
  sources, a duplicate keeps a list source and loses another form's answers).
- The edit operations of the AI chat and MCP do not set a source (the builder and the form spec API do, for lists;
  another form's answers only the builder).
- No per-change history of a list: the last editor and revision are kept, and every change is logged with ids and
  counts only.
