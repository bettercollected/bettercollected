# Reusable sections

A reusable section is a group of questions saved once in the workspace's library and copied into forms: applicant
details, an address block, a consent paragraph. It is built for organisations that keep the same questions in many
forms.

The feature is behind the server setting `REUSABLE_SECTIONS_ENABLED` (off by default). While it is off the library's
routes answer 404, the Insert menu shows no sections, and the operation that inserts one fails. A form that already
holds a copy is not affected: a copy is an ordinary set of questions.

## What a section is

A section has a name, an optional description, a **version** and the **content of that version**: its questions and
(optionally) layout containers, stored in the shape of one page of the [form spec](spec/README.md) (`fields` and
`containers`). Because it is a spec fragment, a save is validated the way a form is: the same spec check, and the
same switches (field rules, the newer question types, choice logic, layout containers, option sources). A section
cannot hold anything a form could not take on this server.

Its questions have ids of their own (made at save, never a form's ids), so one section can be copied into any form,
and into one form any number of times.

## Saving a section

In the form builder, a question's inspector has a **Library** section: "Save as reusable section" for the question,
and, when the question is in a panel, field set or tabs, for that container with all its questions (the container
inspector has the same button). To save several questions, put them in a container first.

Only what points **inside** the section can stay. Everything that points outside is dropped on save, and the builder
lists it afterwards in plain language:

| Dropped | Why |
|---|---|
| a show/hide rule, option filter, date rule or field rule that reads a question outside the section | the question will not exist in the form it is copied into |
| an answer pipe of an outside question, or of a hidden field | same; hidden fields belong to the form |
| a calculation that reads a question outside | it cannot compute; the calculation is left out, and what read it loses the reference |
| a layout container's rule that reads an outside question | same |
| an option source of another form's answers | access to that form is checked where the source is set, not by the library |
| a list source of a list that is not this workspace's | a list belongs to its workspace |
| "answers may be shown as choices" | a new decision for each form |

References **into** an inserted copy from the rest of the form are ordinary references.

Limits: 50 questions per section (a repeating group's questions count), 10 containers, 200 sections per workspace,
200 KB of content per version, a name of at most 100 and a description of at most 500 characters.

## Inserting is a copy

Inserting copies the section into the page: every question gets a new id, every reference inside the copy is
remapped to the copy's own questions (show/hide rules, choice logic, option filters, list parents, date rules, field
rules, calculations, answer pipes in titles and `{{field:...}}` tokens, repeating-group item titles, container
members), rule ids and container ids are new, and each question carries a marker
`properties.library = {sectionId, version, key, instance}`:

- `key` is the question's id inside the section (what makes "update from library" possible),
- `instance` is one id per insert, so two copies of a section in one form stay apart.

The server checks that no reference of the copy names anything but a question of the copy (a stored section that
points elsewhere has that reference dropped, and an insert that still escaped is refused), so an inserted question
can never point at a question of another form. The copy is then saved by the ordinary builder save, which applies
every server check to it. A published form never changes by itself.

The webapp inserts with the editor operation `splice_fields` (one undo step). The marker is the creator's business:
it is removed from the form a respondent gets, and a copy to another workspace (a template, an import) drops it. A
duplicate inside the workspace keeps it; duplicating a page in the builder does not.

## Updating a copy from the library

Each content save (from "Save this copy to the library as a new version" on an inserted question) raises the
section's version. The previous 9 versions stay readable.

"Update from library" on a copy shows a **diff** against the newest version, then replaces the copy where it was:

| Question | What happens |
|---|---|
| in both, same type | **keeps the form's question id** (stored answers and every outside reference stay valid) and takes the library's definition |
| only in the library | added, with a new id |
| only in the copy, or its type changed | removed (a retyped question is removed and added again: answers stored under the old id were given to a question of another shape); references to it elsewhere in the form are pruned like any removal |
| added to the copy by hand | left where it is |

The diff says per question what changed (title, type, required, options, rules, ...), and whether the copy's own
question was changed in the form since the insert (known while the version it came from is still kept). The update
changes the draft only.

Deleting a section never touches the forms that copied it.

## Permissions

| Action | Permission |
|---|---|
| list, read, preview a version | `form.read` |
| create, save a version, rename, delete, insert, update a copy | `form.edit` |

Every call names the workspace; a section of another workspace is a 404, also through the operation path. Library
content never leaves the workspace: no public route, no export, nothing in a template.

## API

`/api/v1/workspaces/{workspace_id}/sections` (session auth):

| Route | Notes |
|---|---|
| `GET /sections` | summaries |
| `POST /sections` | `{name, description?, fields, containers?}` in the builder's shape; answers with the section and `warnings` |
| `GET /sections/{id}?version=n` | the section, or an earlier version, in the builder's shape |
| `PATCH /sections/{id}` | rename, description (the version does not change) |
| `PUT /sections/{id}/content` | `{fields, containers?, expectedVersion?}`: the next version; 409 `section_changed` when the library moved |
| `DELETE /sections/{id}` | |
| `POST /sections/{id}/instantiate` | a copy: marked questions with new ids |
| `POST /sections/{id}/update-plan` | `{instance, fields}`: the diff and the replacement |

## Edit operations (AI, MCP, API)

`{"op":"insert_library_section","pageId":"…","sectionId":"…","index"?:0}` copies a section into a page. The ops
engine cannot read the library, so the write path (`persist_ops_to_form`, and the dry run) resolves the operation
first: the section is read **through the form's workspace**, copied and replaced by the editor operation
`splice_fields` with the concrete questions. A section that does not exist, belongs to another workspace, or a
switch that is off all give the same plain failure. The engine itself never inserts a library section.

`splice_fields {pageId, index?, fields, containers?, replaceIds?, replaceContainerIds?}` is builder-only: it inserts
complete questions (ids kept) and optionally replaces top-level questions of the page, checked as a whole save
(so a calculation may read a later question of the same insert).
