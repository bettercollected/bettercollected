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
| `theme` | Colours, background and style; optionally type and shape (`titleFont`, `bodyFont`, `dataFont` from `public-sans`, `atkinson-next`, `archivo`, `besley`, `rubik`, `atkinson-mono`; `titleWidth` `normal` or `expanded`; `radius` `sharp`, `soft` or `round`; `buttonStyle` `filled`, `outlined` or `pill`) a `highlight` colour (`#rrggbb`) and an `inputText` colour (`#rrggbb`, the answers typed in the white input boxes; absent: `primary`). A key left out keeps the look forms had before it existed. |
| `hiddenFields` | URL parameter names captured with each response (names only). |
| `logo` | Position, alt text and whether to use the workspace logo. `url` is read-only: a logo is set by uploading it. |
| `trust` | Purpose, retention text, privacy policy link, retention period, and the identity, editing and submission-number switches. |

A field has an `id`, a `type` and a `title` (plain text, or a rich-text
document that can pipe answers). Depending on the type it also has `choices`,
`validations` (`required`, `minLength`, `maxLength`, `minValue`, `maxValue`,
`pattern`, `minChoices`, `maxChoices`), `colSpan` (1 to 12), `logic` (show or
hide it), `rules` (see [Field rules](#field-rules)), `dateRules`, `whyWeAsk`,
`internal`, and for a repeating group `repeat` and its own `fields`. Unknown keys are refused. Types the builder
no longer offers are marked `deprecated` in the schema: they are still
accepted so that older forms can be read, and validation warns about them.

### Time, day and currency questions

| Type | The respondent | The answer | Settings |
|---|---|---|---|
| `time` | a time box (the browser's own time picker) | `{"type":"time","time":"HH:MM"}`: 24 hours, zero-padded, no seconds, no zone | `minTime`, `maxTime` (`HH:MM`, the earliest not after the latest; an answer on a bound is fine); `label` |
| `day` | three boxes: day, month, year | `{"type":"date","date":"YYYY-MM-DD"}`, the slot of a `date` question | `dateRules` (as a `date` question's), `label` |
| `currency` | the currency (a choice when there are several) and an amount | `{"type":"currency","currency":{"code":"EUR","amount":"12.50"}}` | `currencies` (1 to 10 ISO 4217 codes, the first is the default; EUR when left out), `validations.minValue` and `maxValue` on the amount |

An amount is a plain decimal string: digits, an optional leading `-`, a dot and
at most the currency's own number of decimals (EUR 2, JPY 0, KWD 3; the table
is [`currencies-v1.json`](currencies-v1.json)). A comma, a thousands separator,
an exponent, a leading `+` or a leading zero is refused, so a stored amount reads
the same everywhere. The server refuses an answer with the rule codes
`format` (not a real time, day or amount), `currency` (a currency the question
does not offer), `too_small` and `too_large` (before the earliest or after the
latest time; below or above the lowest or highest amount), `type` and `required`.

As a source (logic conditions, field rules, calculations) a time reads as its
`HH:MM` text and a day as its `YYYY-MM-DD` text; ordered comparisons (`<`, `>=`,
...) compare them as times and dates (a value that is not one never matches;
this holds for `date` questions too). A currency reads as its amount, a number:
`+`, `sum`, `>` and the rest just work, and the code is not part of the value, so
add up amounts of one currency. Field rules may set a time or a day (a
constant or an expression, as for a date) and a currency's amount (in its first
currency). In the exports a time is `HH:MM`, a day `YYYY-MM-DD` and a currency
`EUR 12.50` (code, a space, a dot decimal).

**Rollout.** The newer question types (`time`, `day` and `currency`; the date
range and tags will join them) are behind one server setting,
`NEW_QUESTION_TYPES_ENABLED`, off by default. While it is off, every write
that gives a form such a question, or changes the type or the settings of one
(the limits, the currencies, a day's date rules), is refused with 422
`question_type_disabled`: a form spec document (the public API create and
replace), the builder's whole-form save, the edit operations (the public API,
the MCP server, the AI assistant and the builder's own, in both engines),
templates and imports. The validation of a document warns about them. Questions
a form already has keep working: they are shown, take answers, are exported and
appear in the response view, and a save that leaves their type and settings as
they are (a new title, another position, other questions changed) is
accepted. Stored data is never changed. The workspace permissions answer
(`GET /workspaces/{id}/permissions`) tells the builder, as
`newQuestionTypesEnabled`, so it can offer the types.

Ids are chosen by the writer and must be unique within the form. Logic
conditions and page jumps refer to them; a jump's `target` is a page id or
`"__SUBMIT__"`. A jump to `"__SUBMIT__"` may add `endingId` to show that
ending after submitting instead of the default one. Endings stored before
they had ids are given `ending-<n>` (their position, from 1) when read, so
the same form always shows the same ids.

An answer `pattern` is a regular expression of at most 200 characters that
the whole text answer must match (use `^` and `$`). It uses RE2 syntax, the
engine the server matches answers with (in linear time): there are no
lookarounds and no backreferences, and a pattern RE2 cannot compile is
refused when the form is saved, with RE2's reason. The respondent's browser
does not run a pattern a creator wrote; it only checks the built-in format
presets and "whole numbers only", so a custom pattern is checked when the
answer is submitted, and the respondent is taken back to the question with
the message. A pattern a form already holds that RE2 cannot use is kept until
it is changed (the server does not check it). When an operation, a form saved
with the API or an Open Formulieren import brings such a pattern, it is
refused (the import leaves it out and lists it as not carried).

## Field rules

A question may carry `rules`: ordered rules that require it or make it
optional, make it read-only, set its value, or change its title or
description while a condition holds. `logic` stays the only way to show or
hide a question.

```jsonc
"rules": [
  { "id": "r1",
    "when": { "conditions": [ { "fieldId": "country", "comparison": "IS_EQUAL", "value": "Netherlands" } ] },
    "then": { "required": true, "description": "Needed for Dutch addresses" } },
  { "id": "r2",
    "when": { "expression": { ">": [ { "var": "qty" }, 10 ] } },
    "then": { "setValue": { "expression": { "*": [ { "var": "qty" }, 5 ] } } } }
]
```

- **`id`**: letters, digits, `-` and `_`, unique within the form.
- **`when`**: either `conditions` (with `operator` `AND`, the default, or
  `OR`; the same conditions as `logic`, at most 20) or an `expression` (an
  [expressions-v1](expressions-v1.md) tree over the form's variables, active
  when its value is truthy: not empty, not `false`, not 0). Never both.
- **`then`**: at least one of
  - `required`: `true` requires the question, `false` makes it optional;
  - `readOnly`: `true` (respondents cannot change the value);
  - `title` (at most 300 characters) and `description` (at most 1000):
    plain text that replaces the question's own; it may pipe answers
    (`{{field:<id>}}`, `{{hidden:<name>}}`);
  - `setValue`: `{"const": <value>}` or `{"expression": <tree>}`.
- At most 8 rules per question and 100 per form.

**What the rules mean.** A question's rules apply in order, and for each
property the last active rule wins; `required` starts from
`validations.required`. The server replays the rules on every submission
and every edit of a response, with the answers as submitted, and is the
authority:

| Effect | While its rule is active | On the server |
|---|---|---|
| `required` | the question must be answered (`true`) or may be left empty (`false`) | Required uses this flag, on the respondent's path, per item in a repeating group |
| `readOnly` | respondents cannot change the value | a submitted value is discarded: replaced by an active `setValue`, else removed |
| `setValue` | the question holds the computed value (and is read-only) | the server computes it and stores it, whatever a client sent; an empty result leaves the question unanswered |
| `title`, `description` | the text respondents read | nothing (presentation only) |

When a value rule is not active, the respondent's own answer stands. A
question whose value a rule sets or locks is never required and its answer
rules (lengths, values, pattern) do not apply: an empty or unusual result of
the form's own rules is not the respondent's to fix. A question hidden by
`logic` or on a page the respondent skips is never required either.

**Where rules may sit, and what they may read.**

- Rules sit on questions respondents answer with one answer: not on pages,
  content blocks, calculated fields, groups themselves, matrices, file
  uploads, tables, payments or internal fields.
- `readOnly` and `setValue` apply to short and long text, number, date,
  yes/no and single-choice questions on a page (not inside a repeating group).
  A choice question is set with `const`: the `id` of one of its options. A
  `const` must fit the question (a number, `true`/`false`, a `YYYY-MM-DD`
  date, a text).
- Conditions and expressions read what logic and calculations read: page
  questions by id, a repeating group's question across its items as
  `<group id>.<question id>`, declared hidden fields by name, calculated
  fields. Inside a repeating group, conditions and expressions read the same
  item's questions by their id (as `logic` does there). A rule never reads
  its own question, an internal field, or a group's question from outside
  the group (use `groupMode` on the group).
- Values that rules set and calculated fields can read each other, but not
  in a circle. The server evaluates them in dependency order, so a condition
  on a calculated or set value sees the final one. Where such a circle is
  stored anyway (data no save accepts), the questions in it have no value
  and are still locked.
- A condition reads a text of at most 10,000 characters (as the inputs of an
  expression do): a longer one counts as empty.

A rule that reads something the form does not have (a question that was
removed, or one respondents are never served, an internal field) is not
active. A rule whose trigger reads a hidden field (a URL
parameter) is controlled by whoever opens the link, as with `logic`: do not
use one to require or lock something the respondent must not escape. Validation and the API refuse a document whose
rules break these rules (`errors` with JSON pointers). The builder's
whole-form save drops a broken rule instead (for example one that reads a
question the save removes) and lists it in the response as
`droppedFieldRules`, as edit operations drop the logic that referred to a
removed question. A form whose rules are too costly to check for each
response (long expressions inside large repeating groups) cannot be saved.

**Rollout.** The form builder has no rule editor yet, and the importers do
not create rules. Rules can come in through a form spec document (the public
API create and replace), the operation `set_field_rules` (the public API, the
MCP server and the AI assistant), the builder's whole-form save, the
builder's edit operations that carry whole questions or pages, and
templates. Until the server setting `FIELD_RULES_ENABLED` is on, each of
these refuses a save that brings new or changed rules (422
`field_rules_disabled`; an operation fails with the same message), and the
validation of a document warns about them; rules already stored are kept and
still enforced. A question that cannot carry rules (for example one made
internal) loses its rules in the builder's save, which lists them in
`droppedFieldRules`.

**Hidden answers.** Rules do not hide anything and keep with the rest of
the form: an answer to a question hidden by `logic` is kept, and a value a
rule sets in a hidden question is stored. One exception exists, unchanged:
the answers of a repeating group hidden by its own `logic` are dropped
before the response is stored, so a hidden group stores no items.

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

`set_field_rules {fieldId, rules}` sets the rules of a question (see
"Field rules" above): `rules` replaces the question's list, in order, and
`null` or `[]` clears it. Each rule is `{id, when, then}` as in the document,
with `when.conditions` written as in `set_field_logic` (a choice by its label,
yes/no as "Yes"/"No") and `$ref:<name>` accepted for a question in a
condition and in an expression's `var`. The operation fails (and the rest of
a non-atomic batch still applies) when the rules break the checks of a save,
or while `FIELD_RULES_ENABLED` is off, unless the rules are the ones the
question already has. Making a question internal removes its rules and
the rules that read it, and says so in the result.

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
- `engines` (optional): the engines that run the case. A case without it is
  run by every implementation; `["backend"]` would mark behaviour the form
  builder's TypeScript engine does not have (no case does today). A case that
  brings field rules assumes the server setting `FIELD_RULES_ENABLED` is on.
- `newQuestionTypes` (optional, default `true`): the state of the switch for the
  newer question types (the server setting `NEW_QUESTION_TYPES_ENABLED`) in
  that case. With `false`, an operation that adds a `time`, `day` or `currency`
  question, or changes the type or the settings of one the form's `before` did
  not have in the same state, fails with a message containing
  `NEW_QUESTION_TYPES_ENABLED`; questions `before` already holds, and edits to
  them that leave their type and settings alone, still apply. Both engines
  read it.
- Ids the operations generate are replaced by `$uuid:1`, `$uuid:2`, ... in
  order of first appearance, walking the form depth first with object keys
  in sorted order. Compare after replacing them the same way.
- Removing a question or a page also removes what referred to it: logic and
  jump conditions on it (a rule or jump left with no conditions goes too),
  answer pipes in titles, date rules and field rules that read it (the whole
  field rule goes). Jumps to a removed page stay, so the
  builder can show them as broken.
- A rich-text title holds only the node and mark types of the builder's
  title editor (`TITLE_NODES` and `TITLE_MARKS` in `ops.py`). Only the form
  builder may send one; elsewhere titles are plain text. A `textStyle` font
  size is 8 to 96 pixels (`"24"` or `"24px"`), a colour `#rgb`, `#rrggbb`,
  `rgb()` or `rgba()` (`backend/backend/app/services/rich_text.py`).
