# API keys: roles, forms and what a key may do

For workspace admins who hand out API keys, and for people who call the
[public API](api/README.md) or the MCP server with one. It says what a key can
do, how that is worked out, what changes it, and what an operator needs to know
before upgrading or rolling back.

A key is a credential for a machine: an AI assistant, a script, an integration.
It acts **as the person who created it**, and it can be limited to less. It is
never given more.

- [What a key is made of](#what-a-key-is-made-of)
- [Roles](#roles)
- [Forms](#forms)
- [How a key's rights are worked out](#how-a-keys-rights-are-worked-out)
- [Making and editing a key](#making-and-editing-a-key)
- [When the creator changes or leaves](#when-the-creator-changes-or-leaves)
- [The switch, and what "off" means](#the-switch-and-what-off-means)
- [Errors](#errors)
- [The audit log](#the-audit-log)
- [Upgrading and rolling back](#upgrading-and-rolling-back)

## What a key is made of

| Part | What it is | Can it change? |
|---|---|---|
| Name | A label for the person who looks at the list. | Yes. |
| Scopes | What the key may do: read forms, write forms, delete forms, read responses, read or act on deletion requests, submit responses. See the table in the [API reference](api/README.md#authentication). | **No.** To change what a key does, make a new key (a new secret). |
| Role | The most the key may do, whatever its scopes: Editor, Reviewer, Viewer or Privacy officer. Optional: no role means "same as its creator". | Yes, by an Owner or Admin. |
| Forms | Every form the key can reach, or only a list of forms. | Yes, by an Owner or Admin. |
| Creator | The person who made the key. The key acts as them. | **No.** |

Only an **Owner or an Admin** (who hold the permission to manage security
settings) can see, make, edit or revoke keys. Keys belong to the workspace and
work in that workspace only.

## Roles

A role limits a key to what a workspace member with that role may do. It is a
ceiling: it never adds anything to what the creator may do.

| Role | Can carry these scopes | Cannot carry |
|---|---|---|
| Same as its creator (no role) | all of them | nothing is ruled out by the role |
| Editor | read forms, write forms, delete forms, read responses, submit responses | deletion requests |
| Reviewer | read forms, read responses | write, delete, deletion requests, submit |
| Viewer | read forms, read responses | write, delete, deletion requests, submit |
| Privacy officer | read forms, read and act on deletion requests | answers (read responses), write, delete, submit |

- Owner and Admin are not roles a key can have. They add nothing a key needs:
  an Owner or Admin who makes a key and chooses no role already gets the full
  set.
- A Reviewer or Viewer key that carries `responses:read` can read responses in
  bulk (list and read them through the API), because that scope is how the
  admin accepted that the key hands out answers. Without the scope it reads no
  answers.
- A role that cannot carry one of the key's scopes is refused when the key is
  made or edited, naming the scope (400 `scope_not_allowed_by_role`).

## Forms

A key's forms are one of:

- **Every form its role can reach** (the default): all the forms the creator
  may use, narrowed by the role.
- **Only the forms I pick** (a list): the key reaches nothing but the forms on
  its list, up to 200.

A key limited to a list:

- **Cannot create forms.** It could not open what it made, and adding the new
  form to its own list would be an increase of access made by a secret, not by
  an admin. The public API's `POST /forms` and the MCP tools that create a form
  answer 403 `key_form_scope`.
- **Cannot carry** `forms:delete` or `deletion_requests:read` and
  `deletion_requests:write`. A form on a key's list gives it the form's content
  permissions and never deleting the form or the privacy programme. These are
  refused when the key is made or edited (400
  `scope_not_allowed_for_listed_key`).
- **Treats a form that is not on its list exactly like a form that does not
  exist**: 404, with the same body, before the request is read and before any
  rate-limit budget is spent. A key cannot be used to find out which forms
  exist.
- **Lists only its own forms** (`GET /forms`, the MCP `list_forms`).
- Can still check a document (`POST /forms/validate`) and read the workspace's
  AI profile, which touch no form.
- With `submissions:write`: the forms it may submit to are the forms on its list
  (the dashboard folds the two together). A key made through the API with both a
  list and a list of forms it may submit to must keep the second inside the
  first (400 `submission_form_outside_list`). Both limits apply on a submission:
  a form outside the list of forms the key may submit to answers 403
  `form_not_allowed`, and a form off the key's list answers 404
  (see [submissions](submissions-api.md)).

The forms the person setting a list may pick are the ones they can open
themselves. A form they cannot open answers as a form that is not in the
workspace (400 `form_not_in_workspace`).

## How a key's rights are worked out

```
what a key may do on a form =
      what its creator may do on that form, right now
  ∩   what its role allows         (no role: no limit)
  ∩   what its list allows         (no list: no limit; not on the list: nothing)
```

Three things follow from this and are worth knowing:

1. **A key never has more than its creator.** The role and the list only
   narrow. A key whose creator is an Editor does not become an Admin because
   it was given a role. Nothing is ever added.
2. **It is worked out again on every request.** Nothing is remembered between
   requests, so a change is effective on the key's next call: a creator who is
   demoted, a form that becomes restricted, a form taken off the list. There is
   no waiting for a token to expire.
3. **The creator's side comes first.** When a call fails because the creator
   no longer has the permission, the answer is 403
   `key_creator_lacks_permission`. When the creator has it but the key's role
   (or a list entry) does not, it is 403 `key_role_lacks_permission`, naming
   the permission.

On every request the order is: the key and its scope, the creator's workspace
permissions, the key's role, and for a call on a form, the creator's access to
that form (restricted forms and grants included, see
[the access model](enterprise-access-model.md)), the key's role and the key's list.

### Keys that already exist

Every key made before roles existed has no role and no list. It is shown as
"Same as its creator" and "All forms", and **nothing changes for whoever holds
it**: it does what it did. There is no automatic limiting, because that would
break running automations. When the switch is on, the key page shows how many
keys still follow their creator, as a reminder to limit them to what they need.

## Making and editing a key

On the dashboard, **AI → MCP** (`/<workspace>/dashboard/ai/mcp`), while the
server has key roles on:

- **Role.** A new key starts on the lowest role that allows the scopes you
  tick, and the page says so. You can pick another, or "Same as its creator".
- **Forms.** "Every form this role can reach", or "Only the forms I pick" with a
  search, "pick all shown" and a count out of 200. Drafts and restricted forms
  are listed too (restricted ones with a Restricted label).
- A combination the server would refuse (a role that cannot carry a scope, a
  list with `forms:delete`) is explained on the page before anything is sent,
  and the scope boxes it rules out are greyed out with the reason.
- **Edit** changes the name, role and forms. The scopes are shown but cannot be
  edited.

### Widening

An edit **widens** a key when it gives it more reach: a role that allows more,
"every form" in place of a list, forms added to the list, or clearing a role
back to "same as its creator". The edit dialog warns first ("You are giving this
key more access. Whatever holds its secret gets it too.") and its button reads
"Widen and save". Narrowing (a lower role, a shorter list, a new list on a key
that had none) needs no warning. An Owner or Admin may widen a key. It is
recorded in the [audit log](#the-audit-log) as a change that widened.

Clearing the role, or lifting the list, makes the key follow its creator, which
may be someone who can do more than you can: the person making the change must
hold every permission the creator holds now, else 403 `key_exceeds_editor` (an
Admin cannot make a key follow an Owner; an Owner can). A role for a key may not
allow more than the person who made it may do (403 `key_role_exceeds_creator`).

### Two people editing the same key

An edit is worked out against the key as it was read. If somebody changed the
key meanwhile (name, role, list, scopes or creator), the edit is worked out
again, up to three times; if it still cannot be made, the answer is 409
`key_changed`. The dialog offers **Reload and try again**, which reads the key
as it is now and starts from it. A key revoked meanwhile cannot be changed (409
`key_revoked`). A last-used update is not a change.

### Over the API

These routes use the dashboard's session, not an API key (a key cannot create
or edit keys). They need the permission to manage security settings.

| Route | What it does |
|---|---|
| `GET /workspaces/{id}/api-keys` | Every key, with `role`, `formScope` and `forms` (ids, and titles where the reader may open the form). Shown as stored, whatever the switch says. |
| `POST /workspaces/{id}/api-keys` | Make a key. Takes `name`, `scopes`, and `role`, `formScope`, `formIds` (the three only while the switch is on). The secret is in the answer, once. |
| `PATCH /workspaces/{id}/api-keys/{keyId}` | Change `name`, `role`, `formScope` and `formIds` (only those; anything else is refused). A field left out stays as it is; `role: null` is "same as its creator". 422 `api_key_roles_off` while the switch is off. |
| `DELETE /workspaces/{id}/api-keys/{keyId}` | Revoke a key. Its list of forms goes with it. |

An id that is not a key, a key that does not exist and a key of another
workspace all answer the same 404.

## When the creator changes or leaves

A key is only as strong as the person it acts as, and is worked out on every
request (above). So:

| What happens to the creator | What the key does |
|---|---|
| Demoted (say Admin to Reviewer) | Its rights shrink on the next request, to what the new role allows. If the person is promoted again they grow again, never beyond the key's own role and list. |
| Role loses a permission a scope needs | The scope stops working (403 `key_creator_lacks_permission`) while the key stays. |
| Workspace disabled (its plan lapsed) | The creator's permissions are then what a disabled workspace allows (read-only for owners, nothing for other members), and the key follows. Nothing is revoked: when the workspace is enabled again the key works as before. |
| **Removed from the workspace** | The creator's keys in that workspace are **revoked**, not just refused. Inviting the person again does not bring them back. |
| **Account deleted** | Their keys are revoked. |
| **Deprovisioned by the directory** (SCIM) | Their keys in that workspace are revoked as their membership is disabled. Provisioning them again does not bring the keys back. |
| **Workspace deleted** | All its keys are revoked. |

Revoked keys stay in the list, marked revoked, so the audit trail and "last
used" remain. Each revocation is written to the audit log first, with the reason
(`member_removed`, `account_deleted`, `scim_deprovisioned`, `admin`,
`workspace_deleted`); removing a member is refused (503) if the entry cannot be
stored. These revocations do not depend on the switch.

## The switch, and what "off" means

Key roles are controlled by the server setting **`API_KEY_ROLES_ENABLED`**. It
is **off by default**, it is read from the server's environment (not the admin
portal), and it applies to the whole instance. The setting is listed in
[settings-inventory.md](settings-inventory.md).

What the switch changes:

| | Off | On |
|---|---|---|
| Make a key without a role or list | Works as it always did. | Works. |
| Make a key with a role or a list | 422 `api_key_roles_off`. | Works. |
| Edit a key (`PATCH`) | 422 `api_key_roles_off`. | Works. |
| The dashboard | Today's page: no role or forms controls, no Edit, no role chips on keys without limits. | Role, forms, Edit, chips, the reminder. |
| A key that has no role and no list | Decided exactly as before, with no new database query. | Same. |
| **A key that already has a role or a list** | **Still enforced.** | Enforced. |
| List and revoke | Work. The list shows what is stored. | Work. |
| Audit of creating and revoking keys | Written. | Written. |

**Off never widens a key.** The switch gates *setting* a limit, not *obeying*
one: a key given a role or a list while the switch was on keeps it when the
switch is turned off, and the dashboard still shows its role and forms, read
only (without an Edit). To let such a key do more, turn the switch on again and
edit it, or make a new one.

The switch is independent of `FORM_ACCESS_ENABLED`: a key's role and list are
enforced whether or not forms can be restricted. With both off, nothing changes
for anyone.

## Errors

On the key routes (the dashboard's), the body is `{"code": "...", "message":
"..."}`. The dashboard shows each in the language of the page.

| Code | Status | Meaning, and what to do |
|---|---|---|
| `api_key_roles_off` | 422 | The server has key roles off. Ask whoever runs it, or make the key without a role or a list. |
| `invalid_key_role` | 400 | Not a role a key can have: Editor, Reviewer, Viewer, Privacy officer, or none. |
| `invalid_form_scope` | 400 | `formScope` is `all` or `listed`. |
| `form_ids_required` | 400 | A list needs `formIds` (empty for a key that opens no form). |
| `form_ids_need_listed_scope` | 400 | `formIds` only goes with `formScope: "listed"`. |
| `form_not_in_workspace` | 400 | A form in the list is not in this workspace, or you cannot open it. |
| `scope_not_allowed_by_role` | 400 | The role cannot carry the named scope. Pick another role, or make a new key. |
| `scope_not_allowed_for_listed_key` | 400 | A list cannot carry the named scope (`forms:delete`, `deletion_requests:*`). |
| `submission_form_outside_list` | 400 | A form the key submits to is not on its list. |
| `unknown_key_scope` | 400 | The key carries a scope this server no longer knows. Revoke it and make a new one. |
| `key_role_exceeds_creator` | 403 | A role cannot allow more than the person who made the key may do. |
| `key_exceeds_editor` | 403 | Clearing the role or the list would make the key follow somebody who may do more than you. |
| `key_changed` | 409 | Somebody changed the key while you edited it. Reload and try again. |
| `key_revoked` | 409 | A revoked key cannot be changed. |

On calls made **with** a key:

| Code | Status | Meaning |
|---|---|---|
| `missing_scope` | 403 | The key was not given the scope. |
| `key_creator_lacks_permission` | 403 | The person who made the key no longer holds the permission (or has left, or is disabled). |
| `key_role_lacks_permission` | 403 | The key's role does not allow the named permission. |
| `key_form_scope` | 403 | The key is limited to a list of forms, so it cannot create a form. |
| (none) | 404 | The form does not exist, or is not on the key's list, or is closed to the creator: the same answer for all three. |

## The audit log

Making a key, changing its role or its list, adding or removing a form, and
revoking a key are each written to the workspace's [audit log](audit-log.md)
before the change is made (and the change is refused when the entry cannot be
stored): `api_key_created`, `api_key_role_changed`, `api_key_scope_changed`,
`api_key_form_added`, `api_key_form_removed` and `api_key_revoked`. Entries hold
ids and values, such as the key's id, role and number of forms, never its name,
prefix, secret or a form's title. A change that widened a key says so.

Every call a key makes is recorded separately in the workspace's API audit log
(the tool or route, whether it worked, no request body).

## Upgrading and rolling back

### Upgrading

Nothing needs doing. There is no migration and no new table: a key's role and
form scope are two new fields in its existing record, a key's list is rows in
the existing form-access table. Every existing key keeps working unchanged. The
switch is off until you turn it on.

Two things come with the release whatever the switch says: keys of members who
leave are revoked ([above](#when-the-creator-changes-or-leaves)), and the MCP
server counts a key's tool calls against the same per-key and per-workspace
ceilings as the REST API ([limits](api/README.md#limits)), so an agent that
makes more than 120 tool calls a minute with one key must slow down or the
instance must raise `API_PUBLIC_API_REQUESTS_PER_WINDOW`.

### Rolling back to a release before 4.4 (F8)

A release before 4.4 does not know a key's role and form scope. **The first time
a key is used on that release, it saves the key's record back without them.**
The key then has no role and no list: it acts as its creator, on every form.
Rolling forward again does not bring the limits back, so **a key that was limited
becomes unlimited**, which is a widening nobody asked for.

Nothing is lost for a key nobody uses, and a rollback with no limited keys in
use is free (that is also the case when the switch was never turned on).

What to do, before rolling back:

1. **List the limited keys that are still live.** On the database (run it
   yourself, with access to the instance's PostgreSQL):

   ```sql
   SELECT id, workspace_id,
          doc->>'role'       AS role,
          doc->>'form_scope' AS form_scope
   FROM app.workspace_api_keys
   WHERE NOT revoked
     AND (doc->>'role' IS NOT NULL OR doc->>'form_scope' = 'listed');
   ```

   Keep the result: it is the only record of which keys carried limits.
2. **Revoke each of them** on the key page (a revoked key is not touched by the
   older release). Tell whoever uses them: after the roll-forward they need new
   keys with the limits set again.
3. Roll back.
4. After rolling forward, make new limited keys. If you could not revoke a key
   before rolling back, assume it lost its limits and revoke it too.

If you rolled back already: every key from the list above that was used since
may now be unlimited. Revoke them all (from the saved list, or from the audit
log's `api_key_created`, `api_key_role_changed` and `api_key_scope_changed`
entries, which name the keys), and make new ones once you are back on 4.4.

Leftover rows of a key's list in the form-access table decide nothing for a key
whose stored scope is `all`, so they do no harm on roll-forward.

## Related

- [API reference](api/README.md): authentication, scopes, limits and errors of the REST API.
- [enterprise-access-model.md](enterprise-access-model.md): the design this follows (section 4).
- [submissions-api.md](submissions-api.md): the `submissions:write` scope.
