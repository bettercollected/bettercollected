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
| `welcomePage` | Title, description, layout, image and button text of the first screen. |
| `pages` | The question pages in order. Each page has an `id`, an optional `sectionTitle`, `layout`, `imageUrl`, `theme` override, `showQuestionNumbers`, flow-view `position`, `jumps` (branching) and its `fields`. |
| `endings` | The pages shown after submitting. |
| `theme` | Colours, background and style. |
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
`"__SUBMIT__"`.

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
logo settings (`update_logo`) and choices by id (`set_choice`, `add_choice`,
`remove_choice`, `move_choice`). They are checked like a whole-form save
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
  jumps to a removed page, answer pipes in titles and date rules.
