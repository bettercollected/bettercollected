# Expressions v1

Expressions compute values from a respondent's answers: calculated fields, scores and conditional
text. A form stores an expression as a JSON abstract syntax tree (AST); the editor shows it as a
readable formula. This document is the contract for both implementations:

- TypeScript (parser, printer, evaluator, validator): `webapp/src/lib/expressions/`
- Python (evaluator, validator): `common/common/expressions/`

Both run the conformance corpus [`expressions-v1.cases.json`](expressions-v1.cases.json). A change
to behaviour changes the corpus first.

## AST

A node is one of:

- a **literal**: a number, a string, `true`, `false` or `null`;
- an **operator node**: an object with exactly one key, the operator, whose value is the list of
  argument nodes: `{"+": [1, {"var": "f_qty"}]}`;
- a **variable reference**: `{"var": "<key>"}`, where the key is a non-empty string of at most 200
  characters.

JSON arrays are not nodes (there are no list literals), and JSONLogic shorthands such as
`{"var": ["a", 0]}` or a non-list argument are rejected.

### Variables

Expressions read the same values as conditional logic and answer piping, from one flat namespace.
The form integration builds the variables map; the evaluator only looks keys up.

| Key | Value |
|---|---|
| `<fieldId>` | the answer as conditional logic reads it (`getComparableAnswerValue`): text, number, `"Yes"`/`"No"`, `YYYY-MM-DD`, or a list of choices for a multi-select |
| `<hiddenFieldName>` | the captured URL parameter (text) |
| `<groupId>.<fieldId>` | a repeating group's question across its items, as a list in item order (unanswered items are `null`) |

Field ids take precedence over hidden-field names if the two ever coincide. Hidden-field names
(`[A-Za-z0-9_-]+`) cannot contain `.`, so group keys never collide with them. A key that is not in
the map is `null`. Only the map's own keys count (`constructor`, `__proto__` and similar are
`null`).

Variable values are normalised on the way in: `null`/missing, booleans and strings are kept;
numbers become decimals (see Numbers; non-finite or out-of-range numbers become `null`); a list
keeps its items, with nested lists and objects becoming `null` items; any other value is `null`.

Input values are capped, and an over-cap value becomes `null` (never truncated, so a result is
never computed from part of an answer):

- a string over **10,000** code points is `null` (as a list item, that item is `null`);
- a list over **1000** items is `null` (repeating groups allow far fewer items, and multi-select
  answers stay well below this);
- nesting is at most one list level: nested lists and objects are `null` items, as above.

Each variable is normalised once per evaluation, however often the expression references it.

## Values and coercion

Values are `null`, booleans, numbers, strings, and lists (only from variables).

**To number** (arithmetic, ordering, `round`, aggregates):

- a number is itself;
- a string is a number when, after trimming ASCII whitespace (space, tab, CR, LF), it matches
  `[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?` and is in range. ASCII digits only; no
  thousands separators, no decimal comma (`"1,5"` is not a number);
- everything else (`null`, booleans, lists, other strings, `""`) is not a number.

**To text** (`concat`, `length`, `lower`, `upper`, `contains`, display):

- strings as they are; `null` → `""`; `true`/`false` → `"true"`/`"false"`;
- numbers in plain decimal notation: no exponent, no trailing zeros, `-` for negatives, `"0"` for
  zero (`1e-7` → `"0.0000001"`);
- lists → their items' texts, empty ones skipped, joined with `", "` (as answer piping shows
  multi-selects).

**Truthiness** (`and`, `or`, `not`, `if`): `null`, `false`, `0`, `""` and the empty list are
false; everything else is true, including `"0"` and `"false"`.

## Numbers

Numbers are **decimals**, not binary floating point, so `0.1 + 0.2` is `0.3`. A number is kept to
at most **15 significant digits** and at most **15 decimal places**, and its magnitude is below
**10^15**. Every operation result is rounded into that shape **half away from zero**; a result
of 10^15 or more (after rounding) is `null`. Fifteen digits means every number converts to a
JavaScript number and back without loss, so results cross the API as plain JSON numbers.

Numbers that arrive as binary floating point (JS numbers, Python `float`) are read through their
shortest round-trip text (`0.30000000000000004` → 0.3 after rounding to 15 digits). Python
`Decimal` and `int` values are read exactly.

**Rounding** is half away from zero everywhere (`round(2.5)` = 3, `round(-2.5)` = −3,
`round(0.125, 2)` = 0.13), not banker's rounding. This matches what spreadsheet users expect and
what invoices show.

**Display** uses the plain decimal text above. The evaluator never rounds for display on its own;
an author who wants a fixed number of decimals writes `round(x, 2)`.

## Operators

`n` = number coercion, `t` = text coercion. Any argument that fails number coercion makes an
arithmetic result `null`.

| Operator | Arguments | Result |
|---|---|---|
| `+` `*` | 2 or more | left to right, each step rounded |
| `-` | 1 (negate) or 2 | |
| `/` | 2 | `null` when dividing by zero |
| `%` | 2 | remainder with the sign of the dividend (`-7 % 3` = −1); `null` for zero |
| `min` `max` | 1 or more | aggregate rules below; `null` when nothing is left |
| `round` | x, digits = 0 | digits must be a whole number (else `null`), may be negative (`round(1250, -2)` = 1300); values above 15 keep x, below −16 are treated as −16 |
| `floor` `ceil` `abs` | 1 | |
| `==` `!=` | 2 | see Equality; `null` if either side is a list |
| `<` `<=` `>` `>=` | 2 | see Ordering |
| `and` `or` | 2 or more | boolean, by truthiness, short-circuit |
| `not` | 1 | boolean |
| `if` | c1, v1, c2, v2, …, [else] | the value after the first truthy condition, else the last odd argument, else `null` |
| `concat` | 1 or more | text of each argument joined, `null` → `""` |
| `length` | 1 | number of Unicode code points of the text; `null` for `null` or a list |
| `lower` `upper` | 1 | Unicode full case mapping (`upper("straße")` = `"STRASSE"`); `null` for `null` or a list |
| `contains` | haystack, needle | list haystack: some item's text equals the needle's text exactly; otherwise case-insensitive substring of the texts. `false` if either is `null`, `null` if the needle is a list |
| `sum` `count` `avg` | 1 or more | aggregate rules below |
| `date_diff_days` | start, end | whole days from start to end (negative if end is earlier); `null` unless both are valid `YYYY-MM-DD` dates |
| `today` | none | the context's `today` (`YYYY-MM-DD`), else `null` |

**Equality:** `null == null` is true and `null` equals nothing else. If either side is a number,
both sides are compared as numbers when both coerce (`18 == "18"` is true); otherwise they are not
equal. Two strings compare exactly (case-sensitive, `"1.0" == "1"` is false). Two booleans compare
as booleans. Anything else is not equal. `!=` is the negation, and `null` when `==` is `null`.

**Ordering:** if both sides coerce to numbers they compare as numbers (`"10" > "9"`). Otherwise two
strings compare by Unicode code point, which orders `YYYY-MM-DD` dates correctly. Anything else
(`null`, booleans, lists, a number against non-numeric text) is `null`.

**Aggregates** (`sum`, `count`, `avg`, `min`, `max`): the arguments are flattened (a list
contributes its items), and `null` and `""` items are skipped as unanswered. `count` counts what is
left. For the others every remaining item must coerce to a number, otherwise the result is `null`.
`sum` of nothing is 0; `avg`, `min` and `max` of nothing are `null`. `sum({a}, {b})` is therefore a
total that tolerates unanswered questions, while `{a} + {b}` is `null` until both are answered.

**Dates** are calendar dates written exactly `YYYY-MM-DD` (years 0001–9999, proleptic Gregorian),
never instants. The evaluator never reads a clock: `today` comes from the context the caller passes
(the respondent's local date in the browser).

## Limits and errors

- At most **32** levels deep (the root is level 1) and **500** nodes (every literal and operator
  node counts).
- Variable values are capped on the way in (see Variables).
- String literals and string results are at most **1000** code points. Results of `concat`,
  `lower`, `upper` and a string returned by the expression are cut to 1000 code points.
- No loops, recursion, network, clock or user-defined functions.

Evaluation is **total**: user data never causes an error; a type error gives `null`. Only a
malformed AST is an error. The validator walks the AST depth-first (pre-order) and reports
problems in that order with a JSON Pointer path (`/+/1/var`); it stops descending below level 32
and stops entirely at the node limit. `evaluate` raises the first problem.

| Code | Meaning |
|---|---|
| `invalid_node` | not a literal or a one-key object, or an argument list that is not a list |
| `invalid_literal` | a number literal that is not finite or not below 10^15 |
| `unknown_operator` | the key is not an operator |
| `arity` | wrong number of arguments |
| `invalid_var` | `var` without a valid key |
| `unknown_variable` | only when the caller passes the known keys |
| `string_too_long` | a string literal over 1000 code points |
| `too_deep` / `too_many_nodes` | the limits above |

## Formula syntax

The editor shows expressions as formulas and parses them back:

```
round(sum({Costs.amount}) * 1.21, 2)
if({age} >= 18, "adult", "minor")
concat("Hello, ", {First name}, "!")
```

- **Field references** are `{label or id}`. Inside the braces `\}` and `\\` are escapes and
  surrounding spaces are ignored. The parser takes a resolver from label to variable key (and
  rejects unknown fields); the printer takes the reverse mapping, falling back to the key.
- **Numbers**: `12`, `1.5`, `.5`; no exponents. A minus directly before a number makes a negative
  literal (`-5`); `-(5)` is the negate operator applied to 5.
- **Text**: double quotes with JSON escapes (`\"`, `\\`, `\n`, `\t`, `\uXXXX`).
- **Keywords** `true`, `false`, `null`, `and`, `or`, `not` and function names are case-insensitive.
- **Operators**, loosest first: `or`; `and`; `not`; `==` `!=` `<` `<=` `>` `>=` (not chainable);
  `+` `-`; `*` `/` `%`; unary `-`. Binary operators are left-associative; a chain of the same `+`,
  `*`, `and` or `or` becomes one node with all the arguments.
- **Functions**: every other operator is a call: `round(x, 2)`, `if(c, a, b)`, `today()`.

Errors carry the offending range as offsets into the formula (UTF-16 code units, as text inputs
count) and say what to do (`Use == to compare two values.`, `Unknown field {Height}.`). Formulas are
at most 10,000 characters. The printer adds parentheses only where needed, and
`parse(print(ast))` returns the same AST for every valid AST whose number literals already have at
most 15 significant digits and whose variable keys have no surrounding spaces.
