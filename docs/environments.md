# Environments: moving a form from staging to production

Many teams build and test a form in one place and run it in another: a
development or staging workspace first, the production workspace for real
respondents. BetterCollected has no separate "environment" feature for this. **An
environment is a workspace.** Development, staging and production are three
workspaces (on one instance, or on different instances), each with its own
members, roles, API keys, webhooks, email messages, custom domains and
data-protection settings. Nothing from one reaches the other unless you move it.

What you move is the **form document** (the [form spec](spec/README.md)): pages,
questions, logic, rules, calculations, endings, look, hidden field names and
the texts about privacy. `bettercollected promote` copies it from one workspace
to another with the [command line tool](../sdk/python/README.md), shows you what
would change, and writes the result as a **draft**. It never publishes.

## What moves and what never moves

| Moves (the document) | Never moves |
|---|---|
| Title, description, language | **Responses.** Answers are never copied, in either direction. |
| Pages, questions, choices, validations | Webhooks, email messages and connections to other systems: they point at addresses and hold secrets that belong to one environment. Set them up again in the target. |
| Show/hide logic, jumps, rules, calculations | Who can open the form, who it is shared with, teams and grants |
| Endings, welcome page, hidden field names | The form's link (slug) and custom domain |
| Colours, fonts and other look settings | When the form is open, its response limit, whether it is published |
| Trust texts and settings (see below) | The logo file (a logo is set by uploading it) |

The result is always a **draft**: a new form, or the draft of a form you name.
Publishing stays a separate step in the target, with its own checks, so the
people who run the target can look at what arrived first.

### What is adjusted on the way

The target has its own storage and its own lists, so some things cannot be
carried as they are. The command lists each one with a count, never with an
address:

- **Images** stored on another instance are dropped (a form may only use images
  from its own instance's storage and Unsplash photos). Add them again in the
  target. Between two workspaces of the same instance the images are kept.
- **Option lists.** A dropdown fed from a workspace list points at a list of the
  source workspace. With `--list-map` you say which list of the target takes its
  place (see the example below); a list with no entry is dropped, and the
  question needs its options set in the target.
- **Options taken from another form's answers** are always dropped. That is a
  decision for the people who run the target.
- **"Show answers as choices"** is switched off, and the marker that links a
  question to a **reusable section** of the source workspace's library is
  dropped.
- **Answer patterns** the server cannot run (over 200 characters, lookarounds,
  backreferences) are dropped.

Whatever the target still refuses, for example a question type or feature that
is switched off on that instance, or a retention date in the past, is listed
with its place in the document and nothing is written.

### Retention, purpose and privacy link

When you update a form that already exists in the target, **its own retention,
purpose, retention note, privacy policy link and the identity and editing
switches stay as they are.** A staging value must never shorten how long
production keeps answers. Add `--copy-privacy` to copy them from the source;
the command warns when that could make the target keep answers for less time
than it does now. A new form has nothing to keep, so it takes the source's
settings.

## Setting up the two workspaces

1. In each workspace, an admin creates an API key (dashboard, **AI**, **MCP**
   tab). A key works in its own workspace only. The source key needs the
   `forms:read` scope, the target key `forms:write`. See the
   [API documentation](api/README.md).
2. Give the CLI the keys **through the environment, never on the command
   line** (a command line ends up in your shell history and in process lists).
   Name each environment and set two variables for it:

```bash
export BETTERCOLLECTED_STAGING_URL=https://staging.forms.example.org
export BETTERCOLLECTED_STAGING_API_KEY=bc_...      # read from your secret store
export BETTERCOLLECTED_PRODUCTION_URL=https://forms.example.org
export BETTERCOLLECTED_PRODUCTION_API_KEY=bc_...
```

   `<NAME>` in `BETTERCOLLECTED_<NAME>_API_KEY` is the environment's name in
   capitals (`staging` gives `STAGING`; any other character becomes `_`). Two
   workspaces on one instance may leave out the second `..._URL`: the target
   then uses the source's address.

Instead of variables you can use a **config file**, by default
`~/.config/bettercollected/config.yaml` (or the path in `BETTERCOLLECTED_CONFIG`
or `--config`). The file names the address and where the key is. The safest
form points to a variable:

```yaml
environments:
  staging:
    url: https://staging.forms.example.org
    api_key_env: STAGING_KEY      # the name of a variable that holds the key
  production:
    url: https://forms.example.org
    api_key_env: PRODUCTION_KEY
```

You can also write the key into the file (`api_key: bc_...`). The command then
refuses to use a file that other users can read: run `chmod 600` on it. Variables
`BETTERCOLLECTED_<NAME>_...` win over the file. The command never prints a key,
and the tool calls only the two instances you configured.

## Examples

### Look first

```bash
bettercollected promote 6123abc --from staging --to production --dry-run
```

`6123abc` is the form's id in the source. With `--dry-run` the command reads
both workspaces and prints what it would do, and writes nothing:

```text
staging -> production
Adjusted for the target:
  2 image(s) dropped, they are not stored in the target. Add them there.
  1 option source(s) taken from another form's answers dropped (who).
Never copied:
  responses (answers are never copied)
  webhooks, email messages and connections to other systems
  who can open the form and who it is shared with
  the form's link
  when the form is open and its response limit
  whether the form is published (the result is always a draft)
  the logo file
A new draft with 3 page(s) and 14 question(s).
Dry run: nothing was written.
```

### Create a new draft in production

```bash
bettercollected promote 6123abc --from staging --to production
# Created draft 6456def.
```

### Update a form that already exists in production

```bash
bettercollected promote 6123abc --from staging --to production --to-form 6456def --dry-run
bettercollected promote 6123abc --from staging --to production --to-form 6456def
```

The first line shows a readable diff of the production **draft** against what
it would become (`+` added, `-` removed, `>` moved, `~` changed). The second
applies it. If someone edits the production form while you review, the write is
refused and you run the command again. Then publish the form in production when
it is ready.

### Option lists

Lists have different ids in each workspace. Write down which source list
takes which target list, in a JSON or YAML file:

```json
{ "6123list-staging": "6456list-production" }
```

```bash
bettercollected promote 6123abc --from staging --to production --list-map lists.json
```

### A form from a file

`bettercollected pull` writes a form to a file and `bettercollected create`
makes a new draft from one, so a form kept in version control can start in any
workspace:

```bash
bettercollected create signup.json     # uses BETTERCOLLECTED_API_KEY and BETTERCOLLECTED_URL
```

## Copying a form in the dashboard (server routes)

The same move is available from the dashboard for a person who is a member of both
workspaces, on one instance. It is behind the server setting
`FORM_PROMOTION_ENABLED` (off by default, set in the environment, not in the admin
portal, until it is released): while it is off, every route below answers
`422` with the code `form_promotion_disabled`, before anything is read. The public
API, the SDK and the command line are not part of the setting.

| Route (under `/workspaces/{id}/forms/{form_id}`) | What it does |
|---|---|
| `GET /promotion/targets?targetWorkspaceId=...&q=...` | The forms of the target workspace the caller may update, the ones last copied from this form first. `{items: [{formId, title, copiedFromSource}], more}` |
| `POST /promotion/preview` | What copying would do, stored nowhere. Body `{targetWorkspaceId, targetFormId?, copyDataProtection?}`. Answers `valid`, every `errors` and `warnings` entry of the target, `diff` (for an existing target), `adjusted`, `notCarried` (counts), `copyIsRestricted`, `retentionShortened`, `targetChangedSinceLastPromotion`, and the `sourceEtag` and `targetEtag` to send back |
| `POST /promotion/apply` | Copies it as a draft. The same body plus `sourceEtag` (and `targetEtag` for an existing form), and a required `Idempotency-Key` header. `201 {formId, workspaceId, created, etag, notCarried, adjusted}` for a new form, `200` for an updated one |
| `GET /spec-file` | The form's document as a download for taking it to another instance (no answer in it). Never cached |

- **Both sides are checked for the same person.** `form.read` on the source form, and
  `form.create` in the target workspace, or `form.edit` on the target form. A workspace
  the caller is not a member of answers as one that does not exist. A **restricted**
  form can be copied only by an Owner, an Admin or its creator (`403`
  `promotion_from_restricted_form`). A new form is **restricted** from the moment it
  exists; no grant comes along. An existing target keeps its own mode (copying into a
  form never changes who may open it), so a restricted form is copied onto an existing
  form only when that form is restricted too: otherwise the preview is `valid: false`
  and apply answers `409 target_not_restricted` ("Restrict the target form first").
  `copyIsRestricted` says what the target will be.
- **Counts and origin are for editors.** `notCarried` is `null` for someone who may
  only read the source form, and `promotedFrom` is left out of a form's settings for
  staff who may not edit it.
- **Rate limited.** Preview and the picker share a per-person limit (counted apart
  from apply, which has its own).
- **Stale guards.** If either form changed since the preview, apply answers `412`.
  An existing target that was copied into before and changed since needs
  `overwrite: true` (`409 target_changed` otherwise). A retry with the same
  `Idempotency-Key` returns the first answer and never makes a second form.
- **Retention.** An existing target keeps its own retention, purpose, retention note,
  privacy link and the identity and editing switches unless `copyDataProtection` is
  true. If copying them shortens how long the target keeps answers, apply also needs
  `confirmShorterRetention: true` (`422 retention_confirmation_required`).
- **Option lists are matched by name.** A question fed from a list of the source
  workspace points at the target's list of the same name; a list the target does not
  have is dropped and reported as `listsNotFound`. List contents never move.
- **What is not copied is counted, never shown:** `notCarried` gives the number of
  webhooks, email actions, connected actions (`sheets`) and case system hand-overs of
  the source form, and `alsoNotCopied` names what else stays behind (answers, who can
  open the form, its link, its dates, whether it is published, the logo file). It never
  carries an address, a recipient or a secret.
- **A person, not a key.** An API key's acting user cannot use these routes
  (`403 promotion_needs_session`): a key works in its own workspace only, and a key
  limited to a list of forms cannot create one. With keys use the command line, one
  key for each workspace; creating a form needs a key that is not limited to a list.
- **Recorded.** `form_copied_out` in the source workspace and `form_promoted` in the
  target workspace are stored before the copy (no entry, no copy: `503
  audit_unavailable`), with ids and counts only. They show in the Activity log under
  Forms. The form file download is recorded as `form_copied_out` too.
- **Staff only.** A copied form remembers where it came from (`promotedFrom` in its
  settings: the source workspace and form ids, who copied it and when, a hash, counts).
  Respondents never receive it.

## Good to know

- A form document holds the texts of your form. If people typed real names or
  addresses into titles, descriptions or default values, they are copied as
  they are, so check a staging form that was made from a real one.
- Promotion calls only the two instances you configured. It does not store a
  key anywhere and it does not make the servers talk to each other.
- The target applies its own rules and switches, so a form that uses a feature
  the target does not have is refused with the list of reasons.
- A key never does more than the person who created it may do in its
  workspace, and every call is recorded in that workspace's API audit log.
