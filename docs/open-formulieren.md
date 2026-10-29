# Open Formulieren

[Open Formulieren](https://open-forms.readthedocs.io/) is an open-source form builder (a form.io based
product from Maykin). This page describes how bettercollected works with it: **importing a form exported from Open
Formulieren as a draft form** and **exporting one of our forms as an Open Formulieren import archive**; sending
submissions to a registration system adds its own section here when it ships.

Everything is behind a switch that is **off by default**.

## Import

### Switch

| Setting | Values | Default |
|---|---|---|
| `OPEN_FORMULIEREN_IMPORT` | `off`, `on` | `off` |
| `OPEN_FORMULIEREN_IMPORTS_PER_WORKSPACE_PER_DAY` | 0 to 100000 | `50` |
| `OPEN_FORMULIEREN_ATTEMPTS_PER_WORKSPACE_PER_DAY` | 0 to 100000 | `100` |

* `off`: the upload and the report endpoints answer **410** `open_formulieren_off` (before anything is read) and
  `GET /providers` does not list the import. The review call (`POST .../review`) is the exception: it still works, so
  a form that carries the "needs review" mark can always be cleared and published.
* `on`: a workspace member who may create forms can import; `GET /providers` lists
  `{"providerName": "open_formulieren", "importMode": "on"}` so the webapp can offer it.

The value is read at call time and an unknown value refuses to start. See `docs/settings-inventory.md`.

### What it does

Open Formulieren can export one form as a zip archive (its "Export" action). Uploading that archive creates a **draft**
form in the workspace, built in memory through the same edit operations the builder, the AI and the PDF import use
(`apply_form_ops`) and saved once. It is **never published** and has no custom address.

The draft is marked **needs review** and comes with a report that lists everything that was dropped, converted or
flagged. Open Formulieren features that have no equivalent here are imported as far as possible, flagged, and
reported; none of them is silently lost.

The upload is untrusted data (see Safety below). Nothing in the archive is ever executed, evaluated, rendered or
fetched.

### Endpoints

All paths are under `/api/v1`; bodies are camelCase JSON.

| Endpoint | Permission | Purpose |
|---|---|---|
| `POST /workspaces/{id}/open-formulieren-imports` (multipart, one `file` part) | form create | import; answers 201 with the finished result |
| `GET /workspaces/{id}/open-formulieren-imports/{import_id}` | form edit | read an import and its report again |
| `POST /workspaces/{id}/open-formulieren-imports/{import_id}/review` `{"reviewed": true}` | form edit | mark the import reviewed (or `false`: needs review again) |

Limits: the upload is at most **5 MiB** (413 `file_too_large`); one form per archive.

Imports per workspace per day, and attempts (a refused archive leaves a small record with no content and counts), have limits of their own (429 `import_limit`; the note of a refused attempt holds only its reason, size and hash, never the file name, and is deleted after two days by the hourly `expire_open_formulieren_attempts` job; not shared with the PDF import's), and only a
few imports build at once in a process (503 `import_busy`, with `Retry-After`). Refusals have a stable `code` (400 unless stated): `file_missing`, `file_too_large` (413), `not_a_zip`,
`archive_unsafe`, `archive_too_large`, `archive_incomplete` (`missing`), `archive_json_invalid` (`file`),
`archive_not_a_single_form`, `open_formulieren_version_unknown`, `open_formulieren_version_unsupported` (`version`,
`supported`), `no_importable_fields` (422), `archive_too_complex` (422; also when a build runs past its work budget), `archive_json_invalid` (422 for
something in the file that could not be read), `import_limit` (429), `import_busy` (503), and 410 `open_formulieren_off`.

### Where the result is stored

* The **report** is stored on a `FormImportDocument` (the record the PDF import also uses) with
  `source_kind = "open_formulieren"`. It holds only the report, the source release, the file name, size and sha256.
  **The uploaded archive is not kept.** The record is deleted with its form.
* The **mark** is on the form's workspace settings: `needs_review`, `import_source`, `import_id`
  (`needsReview`, `importSource`, `importId` in the API). **Publishing is refused while it is set**, by every way of
  publishing (builder, API, MCP): 422 `form_not_publishable` with a problem `needs_review` that carries only the
  import's id (`importId`). Marking the import reviewed (`POST .../review`) clears the mark on the draft and on its
  copies; then publishing works. The mark holds whatever the import switch says and whether or not the report still exists; clearing it
  (`POST .../review`) is not behind the switch and, when the report is gone (deleted with its form), clears the mark
  of the forms in the workspace that name the import (the answer is then a stand-in with `status` `removed`).

### The report

`report.items[]`: `code` (`dropped`, `changed`, `flagged`, `ignored`, `noted`), `kind` (`component`, `logic`,
`variable`, `feature`, `setting`, `archive`), `key`, `label`, `reason` (a stable code; the webapp holds the English and
Dutch sentences keyed by it), `severity` (`warning` or `info`), `flag`, `step` (0-based page), `detail`. At most 500
items; a longer report sets `truncated`. A question that asks for a national identity number (a `bsn` component, or
a text question titled like one, or one prefilled from one) is imported as plain text and carries
`flag: "national_identity_number"`: *check you need it*.

### What is mapped

Steps become pages in `index` order, the page's section title is the step name. A step with nothing importable is dropped
(reported `empty_step`).

| Open Formulieren component | Becomes | Notes |
|---|---|---|
| `textfield` | short text | label, help, placeholder, required, max length, pattern |
| `textarea` | long text | pattern is dropped (reported) |
| `email`, `phoneNumber` | email, phone number | |
| `number` | number | min/max; "no negative numbers" becomes a minimum of 0 |
| `currency` | number | `converted_to_number` |
| `date` | date | min/max dates become date rules where they have an equivalent (a fixed day, today) |
| `datetime` | a date plus a "(time)" short text | `datetime_split` |
| `time`, `postcode`, `iban`, `licenseplate` | short text with a pattern | `converted_to_text` |
| `bsn` | short text, 9 digits | flagged as a national identity number |
| `select`, `radio` | dropdown, multiple choice | needs two options; choices from a variable or list are dropped |
| `selectboxes`, `select` with `multiple` | multiple choice (several answers) | min/max selected |
| `checkbox` | yes/no | `converted_to_yes_no`; a *required* checkbox means "must be ticked", a required yes/no only "must answer" (`checkbox_required_not_enforced`) |
| `file` | file upload | types, size and count are not carried (reported) |
| `content` | statement | html reduced to plain text |
| `fieldset` | heading statement, children flattened | its condition applies to everything inside |
| `columns` | children flattened | column size becomes the question's width |
| `editgrid` | repeating group | children limited to the types a repeating group allows |
| `addressNL` | five short text questions in its place: street, house number, addition, postcode, place | `converted_to_text`; see "Addresses" below |
| `signature`, `map`, `partners`, `children`, `npFamilyMembers`, `cosign`/`coSign`, `customerProfile`, anything unknown | dropped | reported |
| a user-defined variable (`formVariables.json`) set by one unconditional calculation | a calculated question, hidden from respondents, after the last question it reads | `changed`, `user_variable_calculated`; see "Variables" below |
| any other user-defined variable | not carried | `dropped`, `user_variable_not_carried`, with `detail.cause` |

Common to all: label becomes the title, description (or, failing that, tooltip) the help text. Every text is reduced
to plain text (tags, attributes and scripts removed, control and direction characters removed, length capped), template
syntax is kept as literal text and never rendered.

**Addresses.** An `addressNL` component holds five answers and offers a lookup of street and place from postcode and
house number (`deriveAddress`; it needs an address lookup service). It becomes five short text questions in the same
place, in this order, titled "<label> – <part>": Street, House number, Addition, Postcode, Place (Straat,
Huisnummer, Toevoeging, Postcode, Plaats when the form's texts are Dutch; a component without a label is called
Address or Adres). The language is read from the archive: the text at the top level of an export is that of the
language it was made in, so it is Dutch when the form's and its definitions' names equal the `nl` translation and not
the `en` one (a component's own label decides for that component); English when the names do not say.

* *Required* (`validate.required`) applies to house number and postcode always, and to street and place when
  `deriveAddress` is on (then they are part of what the source asks for; without it the source never shows them, so
  here they stay optional). The addition is always optional.
* Their format keeps the house letter (one letter) and the house number addition (one to four letters or digits)
  apart; here they are one question, as the Dutch "toevoeging" is written ("a", "bis", "2", "a 2", "a-2"): up to ten
  characters, one or two parts of at most four letters or digits, separated by a space or a hyphen.
* House number: one to five digits (their rule). Postcode: the pattern of a postcode question here, or the
  component's own pattern for the postcode (`openForms.components.postcode.validate.pattern`) when it is accepted;
  the component's pattern for the place (`openForms.components.city.validate.pattern`) is carried the same way.
  A pattern is accepted when RE2 compiles it within the pattern limits; one that is not is reported
  (`validation_not_carried`). Patterns are anchored, see "Patterns" below.
* The help text goes with the first question; a column width with all five.
* One item is reported (`changed`, `converted_to_text`, `detail.componentType` = `addressNL`, `detail.questions` = 5,
  `detail.lookup` = `not_carried`; a warning when `deriveAddress` was on, else info): the lookup is not carried.
* The five questions count against the question limits like any others. A condition or rule that names the component
  or a path in it (`address`, `address.postcode`) is reported as a missing source (`condition_source_missing`), never
  guessed; a rule that hides or shows the component applies to all five. The exporter does not write the address
  component back: our questions leave as text questions.

**Patterns.** Open Formulieren matches `validate.pattern` against the whole answer: its validation adds a leading `^`
and a trailing `$` when the pattern lacks one (`formio/components/utils.py:6-14`, used for the text components at
`formio/components/vanilla.py:130-136, 336-342` and `custom.py:389, 1173`). Ours search the answer, so a pattern that
does not both start with `^` and end with `$` is carried as `^(?:pattern)$` (the same meaning, and the alternation
`a|b` keeps its intended reading). This holds for the short text path and for an address's postcode and place. A
pattern is accepted when RE2 compiles it within the pattern limits and its shape cannot make a browser's backtracking
engine take exponential time (`(a+)+`, `(a|aa)+`, a backreference; see `docs/spec/README.md`, answer patterns); one that
is not is reported (`validation_not_carried`), because the respondent form checks patterns in the browser too.

**Visibility.** A simple `conditional` (`show`, `when`, `eq`) becomes a show/hide rule on the question. JSON logic
rules are read as data, never run: a trigger that is one comparison of a component with a literal (`==`, `!=`, `>`,
`>=`, `<`, `<=`, `!`, `!!`), or an `and`/`or` of up to ten of them, with actions that show or hide components
(`property` `hidden`), becomes a show/hide rule. Our questions hold one rule each: rules meeting on one question are
reduced to one when that is exact (a rule and its opposite, several "hide when" rules), otherwise the question is
imported without a rule and `conflicting_rules` is reported. A component hidden for good (`hidden` with nothing that
shows it) is dropped (`always_hidden`). Everything else is dropped and reported with its reason (`trigger_not_supported`,
`action_not_supported` with the action type: `disable-next`, `step-applicable`, `step-not-applicable`, `variable`,
`fetch-from-service`, `evaluate-dmn`, `synchronize-variables`, `set-registration-backend`, `property` other than
`hidden`).

**Custom code.** `customConditional`, `calculateValue`, `customDefaultValue`, `validate.custom` and component-level
`logic` are never run and never kept; each is reported `custom_script_dropped`.

**Variables.** Component variables are simply the questions (every question is addressable by logic and answer
piping). A **user-defined variable** becomes a *calculated question* (`docs/spec/expressions-v1.md`) only when all of
this holds; otherwise it is reported as before (`user_variable_not_carried`) with a `detail.cause` that says why.

1. Exactly one action in the whole file sets it (an action of type `variable`), and nothing else writes to it: no
   prefill, no service fetch, no other action naming it (`other_source`; `several_rules`; `no_rule`; `duplicate_key`).
2. The rule of that action always fires: its trigger is the literal `true` (`condition` otherwise; a 3.x rule that only
   starts from a step is `trigger_from_step`). We have no "set only when" for a calculation, so a conditional rule is
   never guessed at.
3. The variable is a number: `data_type` `int` or `float` (`not_numeric`).
4. Its value is an expression of the subset below. Anything else is `operator` (with `detail.operator`, cut to 40
   characters) or `operand`; an expression over 60 nodes, 12 levels or 20 arguments is `too_complex`. A division,
   or a value that is just one answer (a bare `var`), needs a variable that starts empty (`initial_value`: see
   below).
5. Everything it reads is a number question we imported (`number`, `currency`; not in a repeating group, not
   `multiple`) or another variable that qualifies. A key that is not imported (a dropped component, a static variable
   such as `now`) is `source_missing` (`detail.source`); `source_not_number`, `source_in_group`, `source_multiple`;
   another variable that did not qualify is `depends_on_variable`; a circle of variables, or one that reads a circle,
   `cycle`; one that reads a variable a *later* rule sets, `order` (their evaluation is a single pass in rule order);
   a variable with the key of a component, `key_collision`. A question it reads must also be one whose value is only
   what the respondent typed: one that another action, a prefill, a service fetch or a script of the source form also
   sets is `source_rewritten`, and one that starts from a default value (not carried over) is `source_default`
   (`detail.source`). A question that something can **hide** is `source_conditional`: it has a show/hide condition of
   its own, a rule shows or hides it (whatever the trigger, also one we could not carry), it sits inside a layout
   component with such a condition or rule (or marked hidden), or its step can be made (not) applicable by a rule or
   starts as not applicable. The same applies to a bare `var`. Their form clears a hidden component's value, so a
   calculation on it has no value there, while a calculated question here reads every answer that was submitted.
   An action whose output mapping is longer than 200 entries is not read to the end and counts as writing every
   variable and every key (`other_source` for a variable, `source_rewritten` for a question it reads).
6. At most 50 per form and within the 1000-question cap (`too_many`, in the file's order), and the form's own rules
   accept it (`rejected`).

The result is a **calculated question** titled with the variable's name (plain text; the key when it has none),
placed on the page of, and after, the last question it reads (after a calculation it reads for a chain; at the end of
the last page when it reads nothing), **hidden from respondents** (computed and stored with each submission, never
shown, as their user-defined variables are not shown), with format "number", and with "unanswered as 0" **off**. One
`changed` item (`user_variable_calculated`, info) is reported; the rule that set it is not reported (it was not
dropped). The variable's **initial value** is not carried: in the original it is only what the variable holds before
the rule has run.

| JSON logic | expressions v1 | Notes |
|---|---|---|
| `{"+": [a, b, ...]}` (2 to 20 arguments) | `+` | the original sums (`json_logic/__init__.py:112-117`) |
| `{"-": [a, b]}`, `{"-": [a]}` | `-` (subtract; negate) | `:119-126`; a third argument is ignored by the original, so it is refused |
| `{"*": [a, b, ...]}` | `*` | `:314` |
| `{"/": [a, b]}` | `/` | `:316`; exactly two arguments (one returns it untouched there) |
| `{"min": [..]}`, `{"max": [..]}` of numbers and answers | `if(x == null or y == null, null, min(x, y))` | `:317-318`; see the guard below |
| `{"var": "key"}`, `{"var": ["key"]}` | `{"var": <question id>}` | a default value or an empty key is refused |
| a number | the number | at most 15 significant digits, 15 decimals, below 10^15; whole numbers are written whole |
| `%`, `if`, `?:`, comparisons, `and`, `or`, `!`, `!!`, `cat`, `in`, `substr`, `merge`, `count`, `today`, `date`, `datetime`, `rdelta`, `duration`, `reduce`, `map`, `missing`, `log`, texts, booleans, `null`, lists | not translated | `operator` or `operand`; `%` keeps the sign of the *divisor* there and of the dividend in v1, so it is not the same operator |

Where the two meet, the translation is exact except where noted:

* **A missing answer.** The original gives no result when any operand has no value (`:339-351`, `:425-433`; used
  by `submissions/logic/actions.py:424-441` at 4.0.6, `:428-438` at 3.5.14). v1 gives no result for arithmetic on a
  missing value too, which is why "unanswered as 0" is switched off. v1's `min` and `max` instead skip missing values,
  so the translation guards them: `min(a, b)` is `if(a == null or b == null, null, min(a, b))` (the guard is only
  exact for plain answers and numbers, which is why `min` and `max` take nothing else).
* **Division by zero.** An error in the original, caught and logged (`submissions/logic/log_utils.py:12-18`): the
  variable keeps what it held before. In v1 the result has no value. On a first evaluation the two agree only when the
  variable started empty, so a division is carried only then (`initial_value`); a later evaluation differs as in
  "What the variable holds between runs" below.
* **Numbers.** The original uses binary floating point, v1 decimals kept to 15 significant digits (`0.1 + 0.2` is
  `0.3` here and `0.30000000000000004` there). The difference never exceeds the float's own rounding error. A result
  of 10^15 or more has no value in v1.
* **A hidden question.** A hidden component is cleared there (`formio/visibility.py:118-132`), so arithmetic on it
  gives no value. A calculated question here reads every answer that was submitted, hidden by a condition or not, so a
  variable reading a question that can be hidden would not agree: it is not carried (`source_conditional`, above).
  An unanswered question has no value in both.
* **What the variable holds between runs.** Open Formulieren saves variable values with the submission step and
  reloads them, so a variable keeps its last *computed* value when a later evaluation gives no result: `a / b` is
  `0.25` after `a = 1, b = 4` and stays `0.25` when `b` becomes `0` (the division fails and is logged), whatever the
  variable started with. A calculated question here is evaluated from the current answers only: it is empty in that
  case. The two do not agree there; ours never shows a value that no longer follows from the answers (arguably the
  better behaviour). The same holds when an operand is cleared. The `initial_value` rule in this list only covers
  the first evaluation.
* **A bare answer.** A variable whose value is just `{"var": "a"}` is assigned even when the result is empty
  (`submissions/logic/actions.py:424-441` and `rules.py:159-170` at 4.0.6: an empty result is stored as empty); only
  an "undefined" result, which a hidden or cleared question gives (`formio/visibility.py:131-132`), assigns nothing
  and leaves the variable as it was. Arithmetic on such a question gives an empty result instead. So a bare answer is
  carried only when the variable starts empty (`initial_value`). At 3.5.14 (`actions.py:438`) there is no such skip.
* **Whole numbers.** An `int` variable keeps what was computed, without truncation, in the original too
  (`submission_value_variable.py:597-605`, `:694-702`, `:362-379`; its initial value alone is checked against the
  type, `variables/utils.py:32`), so a result such as `7 / 2` is `3.5` in both.
* **Rule order.** Their rules are saved in dependency order (`forms/api/serializers/logic/form_logic.py:35-92`); a
  chain is only carried when the file's order already has each variable set before it is read.

The translation walks the expression as plain data against the table above: it is never run, nothing from the file is
passed to an evaluator, and it has an allow-list of six operator names. Depth, node and argument counts are capped
as listed and every node is charged to the import's work budget.

**Form-level settings.** Not carried, each reported: sign-in plugins (`digid`, `eherkenning`, ...), prefill,
payment, appointment forms, registration backends, translations, confirmation email and presentation settings,
schedule and submission limits, the statement of truth. Carried: the title; the retention in days for completed
submissions (`submissions_removal_options.successful_submissions_removal_limit`, 1 to 3650) as the form's own
retention. The privacy policy text and link are global settings of an Open Formulieren instance and are not in an
export, and Open Formulieren has no purpose field: both are noted (`privacy_policy_missing`, `purpose_missing`) and
need to be set before publishing.

### Versions

The archive has no format version; `_meta.json` records the release that wrote it (`of_release`). These series are
read (`ACCEPTED_SERIES` in `services/open_formulieren/limits.py`):

| Series | Evidence |
|---|---|
| 4.0 | real exports of 4.0.6 (fixtures) |
| 3.5 | real exports of 3.5.14 (fixtures in `tests/fixtures/open_formulieren/3.5.14/`) |
| 3.2, 3.3, 3.4 | the source: from 3.2 on the export has the shape of 3.5 minus a few keys the import does not read (see below); no instance of these releases was available, so there is no fixture, and synthetic archives cover the shapes they hold |

A missing or unreadable release is refused (`open_formulieren_version_unknown`), and so is any other series (3.0 and
3.1, which name the sign-in options differently, 2.x, 3.6 and later, 4.1 and later) with the version named
(`open_formulieren_version_unsupported`, the response lists the supported series): a different export may have changed
shape, and guessing could silently drop or misread data. Widening this is one constant.

#### What differs in a 3.x export

Everything else is read exactly as for 4.0 (same entries, same components, same report codes, same limits). The
differences, and what the import does about them (the evidence, with `path:line` at both tags, is in the pull request
that added 3.x):

* **Appointment forms.** 3.x has no form `type`: an appointment form says `appointment_options.is_appointment`. For a
  3.x export that flag is read like 4.0's `type: appointment` (`appointment_not_carried`).
* **Rules that only start from a step.** A form still on 3.x's old logic evaluation may have rules with
  `trigger_from_step` (4.0 removed the old evaluation and the key). Such a rule would act from the first step here,
  earlier than the original, so it is dropped and reported (`trigger_not_supported`, `detail.cause =
  trigger_from_step`); the other rules are imported as usual. How the old evaluation treats hidden values (it cleared
  them; 4.0 removes them) and values of later steps is not mapped: a rule becomes a static condition on the answers,
  as for 4.0.
* **Older shapes.** Releases before 3.5 wrote empty strings where later ones have `null` or no key (`conditional`,
  `datePicker` limits, `errors`, `minTime`/`maxTime`, a `defaultValue` among the translations). The reader treats empty
  and missing alike; tests inject each shape.
* **Keys that exist only in 3.x** (`new_logic_evaluation_enabled`, `new_renderer_enabled`, `internal_remarks`,
  `form_steps` on rules, file-component registration overrides) and **only in 4.0** (`type`, `help_dialog`,
  `help_callout_page`) are not read.

The report's `source version` is the release as written in `_meta.json` (for example `3.5.14`).

### Safety

The archive is untrusted. `services/open_formulieren/archive.py`:

* read in memory, never extracted; no entry name is ever used as a path;
* only the six known entry names are read (`forms.json`, `formSteps.json`, `formDefinitions.json`, `formLogic.json`,
  `formVariables.json`, `_meta.json`); other safe names are ignored and listed; an unsafe name (absolute, `..`, a
  drive letter, a backslash, a link or special file, a duplicate, an encrypted entry, an unusual compression) refuses
  the archive;
* limits are enforced while reading, with streaming caps, never from header sizes: upload 5 MiB, 16 entries, 8 MiB per
  entry and 16 MiB in all once unpacked, and a bound on the central directory so a many-entry archive is refused before
  the zip reader builds a record for each;
* the zip reader builds one record per entry before it can be counted, so the central directory is bounded first, and an archive
  with a zip64 locator (which would hide the real count) is refused;
* text: markup is removed by a single linear scan (never an HTML parser, whose cost on hostile input is not bounded), each text
  is cut to twice its limit first, and one import has a work budget (characters of text and 5 seconds, checked between the form edit operations too), and one import creates at most 1000 questions (statements and groups
  included; more is `archive_too_complex`): beyond it the
  import is refused as too complex. Only a few imports build at once;
* JSON: nesting depth is checked by an iterative scan before parsing (the stdlib parser recurses), non-finite
  numbers are refused, and values are counted;
* nothing is evaluated: there is no JavaScript engine, template engine, JSON logic library, `eval` or `exec` in the
  import (a test of the source keeps it so), and links in the archive (they point at the source instance) are only
  ever read for the identifier at their end, never fetched;
* the upload is read with a cap before it is parsed, and the switch and the permission are checked before the body is.

### Format reference

Facts about the archive come from Open Formulieren **4.0.6** (`open-formulieren/open-forms`, tag `4.0.6`, commit
`2d28cf5276b04298e342c8914f3b0b31cddda8de`; paths below are under `src/openforms/`) and, for the 3.x differences,
tag `3.5.14` (commit `92a999b1e2527d034a3cf84401e15f8113c585be`): form kind `appointments/api/serializers.py:22-30`,
`forms/api/serializers/form.py:206`, `forms/models/form.py:136`; `trigger_from_step`
`forms/api/serializers/logic/form_logic.py:138-148`, `forms/models/logic.py:44`, `submissions/logic/rules.py:25-58`;
the two feature flags `forms/models/form.py:400-410`; the converters 3.5 added `formio/migration_converters.py:278, 358, 377, 389,
406`. Their code is EUPL-1.2: it was read to match formats, and this implementation is our own; no code is copied.

* Export: `forms/utils.py:81-140` (`form_to_json`), `143-150` (a zip of `<name>.json` entries); the metadata file name is
  `forms/constants.py:4`, its content `forms/utils.py:131-137`.
* Import: reads only the five known resources, `forms/utils.py:49-55, 154-161`; no version check (their converters
  adapt older components: `forms/utils.py:397-416`, `formio/migration_converters.py:459-`).
* Only user-defined variables are exported; component variables are regenerated, static ones created per form:
  `forms/utils.py:100-105`.
* Step, definition and form serializers: `forms/api/serializers/form_step.py:67-113`,
  `form_definition.py:64-90`, `form.py:328-` (fields), `740-748` (export serializer).
* Component JSON: `formio/typing/base.py:19-128` (common keys), `formio/typing/vanilla.py`, `custom.py`, `dates.py`;
  component types and their behaviour: `formio/components/vanilla.py` (textfield `103`, email `170`, time `257`, phoneNumber
  `313`, file `454`, textarea `547`, number `590`, checkbox `647`, selectboxes `720`, select `813`, currency `885`, radio
  `925`, signature `978`, content `997`, editgrid `1128`, columns `1232`, fieldset `1267`) and `custom.py` (date `108`, datetime
  `201`, map `262`, postcode `348`, npFamilyMembers `429`, bsn `518`, addressNL `685`, partners `861`, children `1036`, cosign
  `1096`, iban `1116`, licenseplate `1153`, customerProfile `1333`, softRequiredErrors `1403`, coSign `1415`).
* Address: `formio/typing/custom.py:13-14` (`deriveAddress`), `formio/components/custom.py:91-94` (patterns),
  `564-611` (the five answers: postcode and house number required only when the component is, letter and addition
  optional, street and city derived), `685-766` (the component, its empty value and JSON schema, custom patterns at
  `openForms.components.{postcode,city}.validate.pattern`), `formio/formatters/custom.py:93-` (how the answer is
  written), `formio/migration_converters.py:314-321` (`deriveAddress` defaults to false). The same at 3.5.14
  (`formio/components/custom.py:89-92, 547-594, 668-`, `migration_converters.py:300-`). The builder shows street and city only when
  `deriveAddress` is on: `formio-builder` 1.5.0 `src/registry/addressNL/preview.tsx:36-100`.
* Conditions: `formio/visibility.py:23-88`, `formio/registry.py:250-280`, `formio/components/vanilla.py:783-795`
  (selectboxes), `formio/migration_converters.py:247-289`.
* Logic: `forms/models/logic.py:24-`, `forms/api/serializers/logic/form_logic.py`, `logic/action_serializers.py:30-312`,
  action types `forms/constants.py:8-27`, trigger rule `forms/api/validators.py:22-60`.
* Variables: `forms/api/serializers/form_variable.py:148-193`; the action that sets one, `forms/api/serializers/logic/action_serializers.py:62-71`
  (shape) and `submissions/logic/actions.py:379-441` (evaluation: `jsonLogic(value, data, use_var_undefined=True)`,
  an error is logged and the variable left alone, a result of "undefined" changes nothing), a trigger `submissions/logic/rules.py:137-146`.
  At 3.5.14 the same, without the "undefined" case: `submissions/logic/actions.py:383-438`, `rules.py:243`. The
  operators are those of `maykin-json-logic-py` 0.16.1 (their dependency, MIT licence), `json_logic/__init__.py`, as
  cited in the table above.
* Privacy and retention keys: `forms/models/form.py:230-248` (consent and statement of truth switches),
  `335-395` (removal limits and methods); the policy texts are global: `config/models/config.py:433-480`.
* Builder defaults used to shape the fixtures: `open-formulieren/formio-builder` tag `1.5.0`, `src/registry/*/edit.tsx`
  (`EditForm.defaultValues`).

### Tests and fixtures

`backend/tests/app/open_formulieren/` (archive reader and hostile archives, the importer with golden mappings, the
endpoints, authorisation; `test_importer_3x.py` for 3.x; `test_calculated_variables.py` for the variables, with a model
of the original's arithmetic that the translation is held to). The archives in `backend/tests/fixtures/open_formulieren/` are
our own exports of synthetic forms made in a throwaway local Open Formulieren 4.0.6, and in `3.5.14/` of 3.5.14 (see their
READMEs); the golden files beside them are the expected result of each import. Regenerate a golden file with
`OF_UPDATE_GOLDEN=1 uv run pytest tests/app/open_formulieren/test_importer.py` (`test_importer_3x.py` for the 3.x ones)
and read the diff.

## Export

A form can be downloaded as an archive that Open Formulieren's own import accepts (their "Import form" action, or
`POST /api/v2/forms-import`). It is the reverse of the import and reads the same tables (`services/open_formulieren/mapping.py`
holds both directions).

### Switch

| Setting | Values | Default |
|---|---|---|
| `OPEN_FORMULIEREN_EXPORT` | `off`, `on` | `off` |

* `off`: the endpoint answers **410** `open_formulieren_off` before the caller or the form is looked at, and
  `GET /providers` does not list it.
* `on`: `GET /providers` lists `{"providerName": "open_formulieren", "exportMode": "on"}` (with `"importMode": "on"` beside
  it when the import switch is on too; an entry holds only the modes that are on) so the webapp can offer the download.

The import and export switches are independent.

### Endpoint

`GET /api/v1/workspaces/{workspace_id}/forms/{form_id}/open-formulieren-export`

* Needs the **form-read** permission in the form's own workspace (every role holds it); a form of another workspace is a
  404, a non-member a 403, a signed-out caller a 401. The form's **draft** is exported (what the builder shows).
* Answers `application/zip` with `Content-Disposition: attachment; filename="<title>-open-formulieren.zip"` (ASCII only,
  made from the title: `[a-z0-9-]`), `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` and
  `X-Open-Formulieren-Unmapped: <n>`, the number of things listed in the archive's `README.txt` (see below). The two
  headers are exposed to cross-origin callers (CORS `expose-headers`).
* 422 `nothing_to_export` when no question could be exported, 422 `form_too_large_for_export` (with `maxQuestions`, `maxPages`)
  when the form has more questions or pages than our own import accepts (checked before any work, so every export can be read back),
  422 `export_too_large` above 4 MiB.

### The archive

Six entries in their own names and order (`forms.json`, `formSteps.json`, `formDefinitions.json`, `formLogic.json`,
`formVariables.json`, `_meta.json`) plus `README.txt`, deflated, plain files, built in memory. Their importer reads only
the five resources, never `_meta.json` or the README.

* `_meta.json`: `of_release` `4.0.6` (the series we target), `created` (ISO timestamp), `of_git_sha` **empty**: it names
  the commit of the build that wrote the file and this is not that build.
* Links (`url`, `form`, `form_definition`, `form_steps`) use their mock-host convention, `http://localhost/api/v2/...`,
  identifiers only. All uuids are derived from the form's id and the item's place, so exporting the same form twice gives
  the same ids (their import replaces every uuid anyway).
* One step per page, in order, named by the page's section title (else "Page n", "Pagina n" for a Dutch form). A page
  with nothing exportable is left out. The form is `regular`, inactive and has no category or theme.
* Translations: the form has one language, so `translation_enabled` is false and both language slots hold the same text
  (their import refuses a blank Dutch name).
* Retention: `response_expiration_type: days` becomes `submissions_removal_options.successful_submissions_removal_limit`
  with `delete_permanently` (1 to 3650 days); other settings are listed.
* No privacy-policy text or URL (those are global settings there), no statement of truth (`disabled`).

### Reverse mapping

| Ours | Open Formulieren | Notes |
|---|---|---|
| short text | `textfield` | required, max length, pattern (from the regex: one with a lookaround, a backreference or a repeated group that holds a repetition could backtrack on their side and is left out and listed), placeholder, help text |
| long text | `textarea` | required, max length |
| email | `email` | required |
| number | `number` | required, min, max |
| link (`url`) | `textfield` + link pattern | listed as changed |
| phone number | `phoneNumber` | required |
| date | `date` | fixed or "today" limits become `openForms.minDate/maxDate`; a strict "after/before" a fixed date moves by one day; a rule on another question is listed |
| yes/no | `checkbox` | a required yes/no is exported optional (on a checkbox required means "must be ticked"); listed |
| multiple choice | `radio`; with several answers `selectboxes` | min/max choices become `minSelectedCount/maxSelectedCount` |
| dropdown | `select` (`multiple` when several answers) | rules on a multi-select dropdown are listed |
| file upload | `file` | their default file types and size |
| statement | `content` | escaped plain paragraphs, never markup |
| repeating group | `editgrid` | `validate.maxLength` = max items, required = at least one, `groupLabel` = item label |
| other group | `fieldset` | |
| neighbours with a column width | `columns` | `size` = our width, packed in rows of twelve |
| "why we ask" | tooltip | listed as changed |
| show/hide rule, one equality | `conditional` `{show, when, eq}` | "is not" flips show and hide |
| show/hide rule, anything else | `formLogic` `property` `hidden` action with a JSON logic trigger | `and`/`or` triggers are `is_advanced` |

Left out and listed: calculated fields (their formulas are **not** translated), rating, linear rating, matrix, table,
ranking, payment, hidden and every other type with no equivalent; page jumps; show/hide rules inside repeating groups, on
text "contains" / "starts with", on a multi-select dropdown, on a group's items, or that read a question that was left
out; images and videos; the "other" option; answer rules without a place (minimum length, a pattern on non-text);
hidden URL-parameter fields (their count), purpose and consent text, the privacy link, on-submit actions.

### What is never in the archive

Responses and any answer; staff-only (internal) questions (only their count is told, never a title, and no rule may use
one); hidden-field values; secrets and action credentials; workspace, user and respondent ids and emails; logos, covers,
custom addresses and any URL of ours; sign-in, prefill, payment, appointment and registration settings. The export reads
the form definition only and has no access to responses.

Nothing executable is written: no `customConditional`, `calculateValue`, `customDefaultValue` or script of any kind.
Rules are data: `conditional` objects and JSON logic over a fixed set of operators (`==`, `!=`, `>`, `>=`, `<`, `<=`,
`and`, `or`, `var`). Every string is plain text: markup is removed, then `<`, `>` and `&` are escaped again (decoded entities never
become tags; their forms render labels as HTML), every opening brace of `{{`, `{%` and `{#` (which their forms render, overlapping
runs such as `{{{` included) is followed by a space, the form's title included, statements are written as escaped paragraphs, component keys are ASCII and never shadow their static
variables.

### The README

`README.txt` (plain text, English) says what the archive holds and never holds, then two lists: **Left out (n)** and
**Changed on the way (m)**, one line each ("page 2, "Newsletter": ..."). `X-Open-Formulieren-Unmapped` is `n + m`.

### Format reference (export)

At tag `4.0.6`, paths under `src/openforms/`: export shape and entry names `forms/utils.py:81-150`; mock host and link
form `forms/utils.py:66-74`; what their import resets and rewrites (uuids replaced across the text, no category or theme,
inactive) `forms/utils.py:197-262`; form/definition/step fields `forms/api/serializers/form.py:328-`, `form_definition.py:64-90`,
`form_step.py:67-113`; model limits (form name 150, definition name 50) `forms/models/form.py:81`, `form_definition.py:42`;
conditional `formio/visibility.py:23-88`; selectboxes `value[eq]` `formio/components/vanilla.py:783-795`; editgrid maximum
`vanilla.py:1136-1139`; file component and file types `vanilla.py:454-545`, size fallback `submissions/attachments.py:155`;
trigger rule (first operand a `var` unless `is_advanced`) `forms/api/validators.py:22-60`; `property` action
`forms/api/serializers/logic/action_serializers.py:30-60`; static variable names a key must not shadow
`variables/static_variables/static_variables.py:23-40`, `authentication/static_variables/static_variables.py:21-390`;
removal options `forms/models/form.py:335-353`; date limits `formio/typing/dates.py:8-39`. Component shapes follow the
builder defaults (`open-formulieren/formio-builder` tag `1.5.0`).

### Tests

`backend/tests/app/open_formulieren/test_export.py` (every type, rules of every shape, hostile text, the README, filenames,
the round trip: our importer re-reads what we exported, and the only differences are the documented ones) and
`test_export_api.py` (switch, authorisation, workspace scope, no responses or staff-only content in the archive, headers).
The archives were also imported into a local Open Formulieren 4.0.6 (201, with the same number of steps, components and
rules).
