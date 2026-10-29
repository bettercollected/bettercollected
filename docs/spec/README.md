# Form spec v1

A form as a JSON document: everything its creator controls, in one versioned
shape. The JSON Schema is [`form-spec-v1.schema.json`](form-spec-v1.schema.json).

The schema is generated from the models in `common/common/form_spec/models.py`.
After you change them, regenerate it from `common/`:

```bash
uv run python -m common.form_spec.schema
```

A test fails when the committed file is out of date.

## Shape

| Key | What it holds |
|---|---|
| `specVersion` | Always `"1"`. Required. |
| `title`, `description` | The form's title and description. |
| `language` | The language the form's own text is written in: `nl`, `en`, `de`, `fr`, `es`, `it`, `pt`, `pl`, `da`, `sv`, `nb` or `fi`. Respondent pages mark that text with it for screen readers and browsers. A document that replaces a form and leaves it out keeps the form's language; `null` clears it. The operation `set_form_language` sets it too. |
| `welcomePage` | Title, description, layout, image and button text of the first screen. |
| `pages` | The question pages in order. Each page has an `id`, an optional `sectionTitle`, `layout`, `imageUrl`, `theme` override, `showQuestionNumbers`, flow-view `position`, `jumps` (branching) and its `fields`. |
| `endings` | The pages shown after submitting. Each has an `id` (given when left out), an internal `name`, `isDefault` (at most one; else the first ending is the default), `title`, `message`, `buttonText`, `buttonLink`, `layout` and `imageUrl`. |
| `theme` | Colours, background and style; optionally type and shape (`titleFont`, `bodyFont`, `dataFont` from `public-sans`, `atkinson-next`, `archivo`, `besley`, `rubik`, `atkinson-mono`; `titleWidth` `normal` or `expanded`; `radius` `sharp`, `soft` or `round`; `buttonStyle` `filled`, `outlined` or `pill`) and a `highlight` colour (`#rrggbb`). A key left out keeps the look forms had before it existed. |
| `hiddenFields` | URL parameter names captured with each response (names only). |
| `logo` | Position, alt text and whether to use the workspace logo. `url` is read-only: a logo is set by uploading it. |
| `trust` | Purpose, retention text, privacy policy link, retention period, and the identity, editing and submission-number switches. |

A field has an `id`, a `type` and a `title` (plain text, or a rich-text
document that can pipe answers). Depending on the type it also has `choices`,
`validations` (`required`, `minLength`, `maxLength`, `minValue`, `maxValue`,
`pattern`, `minChoices`, `maxChoices`), `colSpan` (1 to 12), `logic` (show or
hide it), `dateRules`, `whyWeAsk`, `internal`, and for a repeating group
`repeat` and its own `fields`. Unknown keys are refused. Types the builder
no longer offers are marked `deprecated` in the schema: they are still
accepted so that older forms can be read, and validation warns about them.

Ids are chosen by the writer and must be unique within the form. Logic
conditions and page jumps refer to them; a jump's `target` is a page id or
`"__SUBMIT__"`. A jump to `"__SUBMIT__"` may add `endingId` to show that
ending after submitting instead of the default one. Endings stored before
they had ids are given `ending-<n>` (their position, from 1) when read, so
the same form always shows the same ids.

An answer `pattern` is a regular expression of at most 200 characters that
the whole text answer must match (use `^` and `$`). The server matches it with
RE2 (linear time); the respondent's browser uses a backtracking engine, so a
pattern whose shape can make that engine take exponential time on a crafted
or unlucky answer is refused when the form is saved: a repeated group inside
a repeated group (also an optional or bounded one) that can split one text in
several ways (`(a+)+`, `(\w+\s?)+`, `(a?|b?){28}`), a repeated group whose
choices start with the same character (`(a|aa)+`), a repeat of something that
can match nothing (`(a?)*`), more than two overlapping repeats in one
sequence, also across a separator they can match themselves (`\d*\d*\d*`,
`.*a.*a.*a`, `a?` twenty times in a row), inline flags (`(?i)`) and
backreferences (`\1`). The check reads the shape of the pattern, never its
running time, and is conservative: `(\w+\s)+` (each round ends in a separator)
and two overlapping repeats are fine. It reduces the risk but cannot prove that
no pattern is super-linear, so the respondent form also tests only answers up
to 1,000 characters in the browser and leaves longer ones to the server.
The cases are in [`pattern-safety.cases.json`](pattern-safety.cases.json), run
by the server and the webapp, which refuse the same patterns with the same
words. A pattern a form already holds is kept (respondents' browsers skip
it and the server still checks it) until it is changed. When an operation, a
form saved with the API or an Open Formulieren import brings one of these
patterns, it is refused (the import leaves it out and lists it as not carried).

## What is not in the document

- Data the server owns: workspace, owner and form ids, timestamps, publish
  state, response counts, sharing settings, actions and their secrets.
- Derived data: positions (`index`), which follow the array order.
- Data only first-generation and imported forms use (the old rule engine,
  provider references, the consent list). Forms that are not built from
  pages have no spec document.

Converting a form to a document and back keeps everything else
(`common/common/form_spec/roundtrip.py` states this as code, and tests
check it).

## Example

```json
{
  "specVersion": "1",
  "title": "Event sign-up",
  "welcomePage": { "title": "Event sign-up", "buttonText": "Start" },
  "pages": [
    {
      "id": "page-1",
      "fields": [
        {
          "id": "name",
          "type": "short_text",
          "title": "Your name",
          "validations": { "required": true, "maxLength": 80 }
        },
        {
          "id": "dinner",
          "type": "yes_no",
          "title": "Will you join the dinner?",
          "choices": [{ "value": "Yes" }, { "value": "No" }]
        },
        {
          "id": "diet",
          "type": "short_text",
          "title": "Any dietary needs?",
          "logic": {
            "action": "SHOW",
            "conditions": [
              { "fieldId": "dinner", "comparison": "IS_EQUAL", "value": "Yes" }
            ]
          }
        }
      ]
    }
  ],
  "endings": [{ "title": "Thanks", "message": "See you there." }],
  "trust": {
    "purpose": "To plan seats and catering.",
    "retention": { "type": "days", "value": 30 }
  }
}
```

## Checking and previewing

- `POST /api/v1/workspaces/{workspace_id}/forms/validate` checks a document
  and returns `{valid, errors: [{path, message}], warnings, compliance}`.
- `POST /api/v1/workspaces/{workspace_id}/forms/{form_id}/ops/dry-run` applies
  edit operations to a copy of a form and returns the resulting document, a
  diff and per-operation results. Nothing is stored.

Both need permission to edit forms in the workspace. A document can be at
most 1 MB, with at most 200 pages and 2000 fields in all (group questions
included); a batch can have at most 200 operations. The MCP server offers
the same as `validate_form`, `dry_run_ops` and `get_form_spec`.

# Edit operations

A form is changed by a list of edit operations, applied in order, each
addressing pages and questions by id. The JSON Schema of every operation is
[`form-ops-v1.schema.json`](form-ops-v1.schema.json), generated from the
models in `backend/backend/app/services/ai/ops.py`. After you change them,
regenerate it from `backend/`:

```bash
uv run python -m backend.app.services.ai.ops_schema
```

A test fails when the committed file is out of date.

Some operations are for the form builder only (listed in `x-editorOnlyOps`,
and marked `"x-editorOnly": true` on their definition): they take whole
questions and pages with the ids the builder chose (`insert_field`,
`replace_field`, `insert_page`), page and welcome page settings
(`update_page`, `update_welcome_page`), hidden fields (`set_hidden_fields`),
logo settings (`update_logo`), choices by id (`set_choice`, `add_choice`,
`remove_choice`, `move_choice`) and the endings as a whole, ids kept
(`set_endings`; page jumps are left as they are). They are checked like a whole-form save
(ids unique in the form, size limits, image addresses, answer patterns,
repeating group rules). The public API, the MCP server and the AI assistant
refuse them, with an error for each such operation.

## Conformance cases

[`form-ops-v1.cases.json`](form-ops-v1.cases.json) lists operations applied
to a form and what they must produce. Any implementation of the operations
should pass every case.

```json
{
  "forms": { "<name>": { "title": "...", "fields": [] } },
  "cases": [
    {
      "name": "what the case shows",
      "before": "<name>",
      "ops": [{ "op": "remove_field", "fieldId": "q1" }],
      "atomic": false,
      "expect": { "form": {}, "error": { "index": 0, "messageContains": "..." } }
    }
  ]
}
```

- `before` is the form the operations start from: the name of one of
  `forms`, a form, or `{"$generated": {"pages": n, "fieldsPerPage": m}}`
  (pages `p<i>` holding short text questions `p<i>f<j>` titled `"Q"`, for
  the size limits). Forms are in the builder's camelCase shape.
- `atomic`: all or nothing. When an operation fails, the form stays as it
  was. Otherwise each failed operation is skipped and the rest apply.
- `expect.error`: the first operation that fails is at `index`, and its
  message contains `messageContains`. The operations before it apply. In an
  atomic case the form is unchanged.
- `expect.form`: the whole form afterwards, with `index` values renumbered.
  It is left out when the form does not change, and for generated forms.
- `expect` without `error` means every operation applies.
- Ids the operations generate are replaced by `$uuid:1`, `$uuid:2`, ... in
  order of first appearance, walking the form depth first with object keys
  in sorted order. Compare after replacing them the same way.
- Removing a question or a page also removes what referred to it: logic and
  jump conditions on it (a rule or jump left with no conditions goes too),
  answer pipes in titles and date rules. Jumps to a removed page stay, so the
  builder can show them as broken.
- A rich-text title holds only the node and mark types of the builder's
  title editor (`TITLE_NODES` and `TITLE_MARKS` in `ops.py`). Only the form
  builder may send one; elsewhere titles are plain text. A `textStyle` font
  size is 8 to 96 pixels (`"24"` or `"24px"`), a colour `#rgb`, `#rrggbb`,
  `rgb()` or `rgba()` (`backend/backend/app/services/rich_text.py`).
