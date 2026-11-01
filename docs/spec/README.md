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
| `trust` | Purpose, retention text, privacy policy link, retention period, the identity, editing, submission-number and review-page switches, and `allowSaveDraft` (let respondents save a draft and continue later, off by default; turning it on is refused with 422 `save_drafts_disabled` while the server setting `SAVE_DRAFTS_ENABLED` is off) with `draftRetentionDays` (1 to 90, default 30). |

A field has an `id`, a `type` and a `title` (plain text, or a rich-text
document that can pipe answers). Depending on the type it also has `choices`,
`validations` (`required`, `minLength`, `maxLength`, `minValue`, `maxValue`,
`pattern`, `minChoices`, `maxChoices`), `colSpan` (1 to 12), `logic` (show or
hide it), `rules` (see [Field rules](#field-rules)), `dateRules`, `whyWeAsk`,
`optionFilter` (see [Choice logic](#choice-logic); a choice also has its own `logic`),
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
the same everywhere; so is a zero written with a minus (`-0`, `-0.00`). An
amount is not below zero unless the question's lowest amount (`minValue`) says
it may be: with no lowest amount, or one of 0 or more, a negative amount breaks
`too_small`, and a negative lowest amount allows negative ones. A `day` has its
year from 1000 on: a year of fewer than four digits ("90") is a typing slip, so
the boxes do not pad it and `0090-11-05` is refused (`format`), as is an end of
a date range in such a year. The server refuses an answer with the rule codes
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

### Date range and tags questions

| Type | The respondent | The answer | Settings |
|---|---|---|---|
| `date_range` | two date pickers, the first and the last day | `{"type":"date_range","date_range":{"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}}` | `dateRules` (as a `date` question's: each end must meet them) |
| `tags` | a box that turns what is typed into removable labels | `{"type":"tags","tags":["vegan","quiet"]}` | `validations.minChoices` and `maxChoices` (the number of tags, at most 30), `validations.maxLength` (one tag's length, at most 40) |

A date range needs both ends once either is typed, and the end is not before
the start (the same day is fine). A tag is stored the way it is shown: trimmed,
not empty, without `,` or `;` (they separate tags in the box and in an export)
or control or format characters (zero-width and bidirectional marks, the byte
order mark, the soft hyphen: they reverse or hide text and defeat the
comparison), and no two tags are the same ignoring case; a question holds at
most 30 tags of at most 40 characters, and its own limits can only be lower
(`maxChoices` 1 to 30, `minChoices` 0 to 30 and not above the most, `maxLength` 1 to 40:
every path that writes a question refuses others, the model, the spec, the builder save
and the operations).
These hard rules hold for every stored tags answer, a hidden or skipped
question's too; the question's own limits are checked for the questions a
respondent answers. The server refuses an answer with the rule codes `format` (a day that
does not exist, a tag that is empty, untrimmed or has a forbidden character),
`required` (only one end of a range), `range_order` (the end is before the
start), `too_long` (a tag over its length), `duplicate`, `too_few_choices` and
`too_many_choices` (the number of tags) and `type`. Another
question's date rule can compare with a `date` or a `day` question, not with a
range.

As a source a date range is two variables, `<id>.start` and `<id>.end` (both
`YYYY-MM-DD`, so `date_diff_days({stay.start},{stay.end})` gives the nights),
and in a repeating group the lists `<group>.<id>.start` and `<group>.<id>.end`.
A logic condition on a range compares it with a day: `CONTAINS` (the range
includes the day), `DOES_NOT_CONTAIN`, `GREATER_THAN` (it starts after the day),
`LESS_THAN` (it ends before the day), `IS_EMPTY` and `IS_NOT_EMPTY`; it needs
both ends and a well-formed day, else it does not hold. Tags read as a list, like
a multiple choice, compared ignoring case and in Unicode form C (a precomposed
and a decomposed letter are the same tag): a condition on them is `CONTAINS`,
`DOES_NOT_CONTAIN`, `IS_EMPTY` or `IS_NOT_EMPTY`, and the spec check and the edit
operations refuse the others (a list has no beginning, end or order; in a
condition, `STARTS_WITH`, `ENDS_WITH` and the ordered comparisons never hold for
a list, a multiple choice's too). A rule on a range cannot read its own
`<id>.start` or `<id>.end`. Field rules do not set the value of either type. In the exports a
range is `YYYY-MM-DD/YYYY-MM-DD` (an ISO 8601 interval, an end that is missing
leaves its side empty) and tags are one cell, joined with `; `, with the CSV's
formula guard as for every cell.

**Rollout.** The newer question types (`time`, `day`, `currency`, `date_range` and `tags`) are behind one
server setting,
`NEW_QUESTION_TYPES_ENABLED`, off by default. While it is off, every write
that gives a form such a question, or changes the type or the settings of one
(the limits, the currencies, the date rules of a day or a range, the number and length of tags), is refused with 422
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

### Signature question

| Type | The respondent | The answer | Settings |
|---|---|---|---|
| `signature` | draws in a box (mouse, finger or pen) or types their name; both always work | `{"type":"signature","signature":{"method":"typed","name":"Fatima El Idrissi","signedAt":"2026-11-01T09:31:12Z"}}` or `{"type":"signature","signature":{"method":"drawn","fileId":"<id>","signedAt":"..."}}` | none besides `validations.required`, a title and a description |

A signature records a drawn or typed name. It does not check who signed, and
nothing in the product says it has any legal weight.

- **Typed:** the name is stored as shown: trimmed, in Unicode form C, 1 to 100
  characters, without control, format (zero-width, bidirectional marks, the byte
  order mark, the soft hyphen) or line and paragraph separator characters.
- **Drawn:** the browser sends a PNG as a file part of the submission, named by the
  answer's `fileId` (a plain id). The server never decodes it in the API process:
  it checks the size (at most 150 KB) and that it is a PNG, then the isolated
  document sandbox decodes it and writes a fresh PNG without metadata (at most
  2000 x 1000 pixels and 1 million pixels). The stored object is that
  re-encoding, a private file under the response's folder, deleted with the
  response (also when its retention runs out, when the form is unlinked from a
  workspace, and when the signature is replaced in an edit). Without the sandbox a
  drawn signature is refused (503, try again); a typed one never needs it.
  The object is stored as `image/png`, and its download link is signed to serve
  `image/png` as an attachment. An image with no ink at all is not told apart without decoding it: the
  respondent form never sends one.
- **`signedAt`** is stamped by the server when the signature is stored; a value
  the client sends is ignored, and an edit that leaves a signature as it is keeps
  its stamp.
- A drawn answer must name an image sent with it for that question (or, in a
  respondent's edit, the image the response already holds); an id with no image,
  an image for another question and two images for one question are refused.
- The server refuses an answer with the rule codes `required`, `type` (another
  shape: a slot of another type, an unknown key, not text), `format` (a method
  that is neither `drawn` nor `typed`, a name with a forbidden character or not
  trimmed or in form C, a name given with an image or the other way round),
  `too_long` (a name over 100 characters) and `signature_image` (a drawn
  signature whose image is missing, not accepted or not named by a plain id).
- **Logic:** a condition on a signature asks only `IS_EMPTY` or `IS_NOT_EMPTY` (the
  spec check and the edit operations refuse the others; a condition that is not
  one of them never holds). A signature is never a formula variable and is not
  piped into a title. **Field rules** may require it, make it optional, or change its
  title or description; never set or lock its value.
- Not allowed inside a repeating group, and never internal.
- **Where it goes:** the dashboard shows the image (a short-lived link on the single
  response view only, never in a list) or the typed name in an italic serif; the CSV
  has the typed name or `[drawn signature]`; the public API and the MCP server return
  the stored answer (no image, no link); webhooks, registrations and email actions do
  not carry it (it is not a variable they can map); the AI insights see `[signed]`;
  action code (the email action and the Sheets row) gets `[signed]` for both methods, never the name.
- A draft keeps a typed signature and not a drawn one (files are not kept).

**Rollout.** The signature question is behind its own server setting,
`SIGNATURE_QUESTION_ENABLED`, off by default, and works like the newer question
types' (see above): while it is off, every write that gives a form a signature
question, or turns another question into one, is refused with 422
`signature_question_disabled` (the builder's save, the spec API, the edit
operations, templates and imports); a signature question a form already has keeps
being shown, answered, exported and read, and a save that leaves it as it is is
accepted. The switch never governs answering. `GET /workspaces/{id}/permissions`
tells the builder as `signatureQuestionEnabled`.

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

## Choice logic

A single choice, multiple choice or dropdown question can offer its options
conditionally. Both forms of it leave the question's own `logic` (show or hide
the whole question) as it is.

```jsonc
{ "id": "drink", "type": "multiple_choice", "title": "Drink",
  "choices": [
    { "id": "soda", "value": "Soda" },
    { "id": "wine", "value": "Wine",
      "logic": { "action": "SHOW",
        "conditions": [ { "fieldId": "age", "comparison": "GREATER_THAN_EQUAL", "value": "18" } ] } } ] },
{ "id": "city", "type": "dropdown", "title": "City",
  "choices": [ { "id": "ams", "value": "Amsterdam" }, { "id": "ber", "value": "Berlin" } ],
  "optionFilter": { "fieldId": "country",
    "mapping": [ { "when": "nl", "show": ["ams"] }, { "when": "de", "show": ["ber"] } ] } }
```

- **`choices[].logic`** is the question-level logic (`action` `SHOW` or `HIDE`,
  `operator`, `conditions`, the same conditions): `SHOW` offers the option only
  while they hold, `HIDE` offers it unless they hold. At most 20 conditions per
  option.
- **`optionFilter`** filters a question's options by an earlier choice
  question's answer: `fieldId` is that question, and each `mapping` row lists
  (by option id) the options offered while its option `when` is chosen. With
  several chosen options (multiple choice) the options offered are the union.
  With no answer to that question (or only "Other" text) nothing is filtered;
  a chosen option with no row offers nothing. The question's options must carry ids.
- An option is **available** when its own logic allows it and the filter lets it
  through. Conditions and filters read the answers as given, hidden or not, as
  `logic` does.

**Where it may sit and what it may read.** Only page-level choice questions
(not inside a repeating group, not internal). A condition or a filter reads an
**earlier** respondent-facing question of the form (never the question itself,
an internal one, or a question of a repeating group; a repeating group as a whole
by `groupMode`), so the evaluation has no circle. A filter's ids name real
options of the two questions. At most 200 options on a question that has option
logic (a save that would drop its logic is refused, saying so, never wiped), 1,000
option conditions and 50 filters in a form, and the worst case of one response
(every option chosen in the questions the conditions read, every group at 50
items) must stay within the server's evaluation budget, or the form cannot be
saved. Validation and the API
refuse a document that breaks these rules (`errors` with JSON pointers); the
builder's whole-form save repairs instead what a structural edit broke (a
removed or moved question, a removed option), so autosave never stops.

**What the server does.** On every submission and every edit of a response,
the server evaluates which options are available from the answers as submitted
and refuses (422 `invalid_answers`, rule `hidden_option`, never the value) an
answer that selects an option that is not available, on a question the
respondent is asked (on their path, not hidden by logic; answers to hidden
questions and skipped pages are kept as ever). An edit also checks the choice
questions whose options read an answer it changed, so an edit that strands a
later selection is reported on that question (send it again with an available
option). The respondent page clears such a selection itself and says so
politely; the server never deletes an answer silently. A question with nothing
available (and no "Other") is never required, `minChoices` is held to the
number of options offered, and a question a field rule sets or locks is not
filtered. With "Other" enabled a respondent can type the label of a hidden
option as free text: that is an answer to "Other", not a selection of the option,
so do not use "Other" on a question whose options gate access.

**Rollout.** Until the server setting `CHOICE_LOGIC_ENABLED` is on (it is off by
default, and stays off until the 4.2 release), every write that brings new or
changed option logic or filters is refused with 422 `choice_logic_disabled` (an
operation fails with the same message): the builder's save, the form spec API
(create and replace), `set_option_logic`, `set_option_filter`, the editor
operations that carry whole questions, templates, and the AI and MCP paths; the
validation of a document warns about them. A provider import never brings any,
and a copy of a page or question starts without option logic. Option logic
already stored is kept and still enforced. The builder reads the switch from the
workspace permissions answer (`choiceLogicEnabled`): with it off the option
logic settings are hidden, and what a question already has is listed read-only.

**Warnings** (never refused): an option no filter row shows, an earlier option
with no row, and a required question whose every option has its own logic.

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

`set_option_logic {fieldId, choice, logic}` gives one option of a page-level
choice question its own logic (`choice` is the option's label or id, `logic` is
written as in `set_field_logic`, `null` clears it) and
`set_option_filter {fieldId, filter}` sets or (with `null`) clears the filter of
a question (`filter` is `{fieldId, mapping: [{when, show: [...]}]}` with the
options named by label or id; stored by id). See "Choice logic" above. Removing a
question or an option removes the conditions and filter entries that read it and
says so in the result; moving a question or page so that an option would read a
later question is refused.

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
  that case. With `false`, an operation that adds a `time`, `day`, `currency`,
  `date_range` or `tags` question, or changes the type or the settings of one the form's `before` did
  not have in the same state, fails with a message containing
  `NEW_QUESTION_TYPES_ENABLED`; questions `before` already holds, and edits to
  them that leave their type and settings alone, still apply. Both engines
  read it.
- `signatureQuestion` (optional, default `true`): the same for the signature
  question (the server setting `SIGNATURE_QUESTION_ENABLED`). With `false`, an
  operation that adds a `signature` question, or turns a question into one, fails
  with a message containing `SIGNATURE_QUESTION_ENABLED`; the other switch
  is not affected by it. Both engines read it.
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
