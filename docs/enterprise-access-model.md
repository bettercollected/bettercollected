# Enterprise access model: roles, permissions and form-level scope

Status: **accepted** (2026-10-03; decisions and open questions confirmed by the product owner). Rollout: steps a and b are implemented, plus several owners per workspace (see *Rollout* and *Owners*); step c (member groups, called Teams, form grants and restricted forms) is built behind the server setting `FORM_ACCESS_ENABLED`, off by default (see *Step c as implemented* and [form-access.md](form-access.md)); d and e are not complete. It is a prerequisite for SSO/SCIM, which is Phase 0 of the enterprise work in [`docs/sso-spike.md` on the `spike/sso-polis` branch](https://github.com/bettercollected/bettercollected/blob/spike/sso-polis/docs/sso-spike.md).

## Decisions (confirmed)
1. **Form-level scoping ships in v1.** Access can be granted on specific forms to users and groups. Folders come later.
2. **The v1 workspace roles** are Owner, Admin, Editor, Reviewer, Viewer and **Privacy officer**.
3. **Export is its own permission.** It covers every way response data leaves the product in bulk.

## Where we are today
- **Platform `ADMIN`** (`PLATFORM_ADMIN_EMAILS`) is the instance operator. It is separate from workspaces and unchanged by this design.
- **Workspaces** have an owner (`owner_id`) and two roles, `ADMIN` and `COLLABORATOR`. A collaborator has full access to content: they can edit any form, read every response and fill internal fields. A few actions are admin-only: AI settings, API keys, members, responder groups and respondent feedback.
- **Checks are made case by case.** Each service asks "is a member" or "is an admin" itself, and there is no list of permissions. As a result the same kind of action is guarded differently in different places; see *Inconsistencies* below.
- **There is no per-form access for members.** `settings.hidden` only hides a form from other members' listings; the endpoints themselves still admit any member.
- **There is no endpoint to change a member's role.** The webapp's "admin" (`selectIsAdmin`) means the owner only, while the backend's means ADMIN or owner.

## Model

```
can(user, permission, workspace, form?)  =
    workspace permission   from the user's workspace role
  ∪ form permission        from form grants (user or member group) on that form
  ∩ form access mode       restricted forms ignore workspace-wide content access
```

### 1. Permissions (the only thing services check)

| Permission | Covers |
|---|---|
| `workspace.manage` | name, handle, branding, themes, custom domain, site settings |
| `workspace.billing` | plan, Stripe, transfer, delete workspace |
| `members.manage` | invite, remove, change roles, member groups |
| `security.manage` | SSO settings (view, test a connection), SCIM, verified domains, API keys. Changing the SSO configuration (connections, "require SSO", the default role) is **owner only** on top: a connection controls every account on the workspace's verified domains, the owner's included ([sso.md](sso.md)) |
| `ai.manage` | AI opt-in and provider, AI profile |
| `audit.read` | audit log |
| `form.create` | create, import (Google/PDF), from template |
| `form.read` | open a form in the dashboard (structure, settings) |
| `form.edit` | edit, publish, duplicate, settings, actions, responder-group links |
| `form.delete` | delete a form |
| `form.share` | form grants and access mode |
| `response.read` | individual answers (incl. AI insights, flow analytics per response) |
| `response.annotate` | internal fields, respondent feedback |
| `response.export` | CSV, API/MCP `responses:read`, integrations and actions that send responses out (sheets, webhooks, email copies) |
| `response.import` | import submissions from a CSV file and undo an import (docs/response-import.md; behind `CSV_IMPORT_ENABLED`) |
| `response.delete` | delete a response |
| `response.edit` | change the answers of a response (needs `response.read` too); behind the server setting `RESPONSE_REVISIONS_ENABLED`; every edit is kept in the response's history ([response-revisions.md](response-revisions.md)) |
| `privacy.manage` | deletion requests, data subjects (responders), consent catalog, retention and privacy texts |
| `analytics.read` | aggregates: counts, Umami stats, drop-off. No individual answers |

### 2. Workspace roles

| Permission | Owner | Admin | Editor | Reviewer | Viewer | Privacy officer |
|---|---|---|---|---|---|---|
| workspace.billing | ✓ | | | | | |
| workspace.manage, members.manage, security.manage, ai.manage | ✓ | ✓ | | | | |
| audit.read | ✓ | ✓ | | | | ✓ |
| form.create | ✓ | ✓ | ✓ | | | |
| form.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (structure only) |
| form.edit, form.delete, form.share | ✓ | ✓ | ✓ | | | |
| response.read | ✓ | ✓ | ✓ | ✓ | ✓ | **✗** |
| response.annotate | ✓ | ✓ | ✓ | ✓ | | |
| response.export | ✓ | ✓ | ✓ | | | |
| response.import | ✓ | ✓ | | | | |
| response.delete | ✓ | ✓ | ✓ | | | |
| response.edit | ✓ | ✓ | ✓ | | | **✗** |
| privacy.manage | ✓ | ✓ | | | | ✓ |
| analytics.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

- **Owner:** a workspace can have **several owners with equal rights**: each holds every permission in the Owner column, billing and the SSO configuration included (see *Owners* below). One of them is the **billing owner**, the account the plan is billed to. A workspace always keeps at least one active owner.
- **Editor** is today's `COLLABORATOR`; existing collaborators migrate to Editor with no behaviour change. A new form is editable by its creator even inside restricted scopes.
- **Reviewer:** reads, annotates (internal fields) and responds to submissions (feedback), but does not change forms. This is the hiring and case-handling role.
- **Viewer:** read-only access to forms and their responses.
- **Privacy officer:** runs the privacy programme without reading answers. They handle deletion requests and see who the data subjects are (respondent identifiers, needed to act on a request). They manage consent, retention and privacy texts, and read the audit log. They cannot read answers, export, or change forms. They **complete** deletion requests: deleting a response that has a *pending* deletion request needs `privacy.manage` (or `response.delete`); any other delete needs `response.delete`. They can also close a pending request by hand (`POST /workspaces/{id}/forms/{form_id}/submissions/{response_id}/deletion-request/close`, `privacy.manage` only), which needs no form provider: `completed` deletes the workspace's stored copy, `declined` keeps it and records one of a fixed list of reasons (`legal_obligation`, `legal_claims`, `public_interest`, `identity_not_verified`, `other`); who closed it and when stay on the request, and a later import from the provider never brings a completed response back. Combined with any other role on the same membership, a Privacy officer still never holds `response.read`, `response.annotate`, `response.export` or `response.edit`. This role is deliberately unusual for a form tool and fits the trust-first positioning.

Respondent feedback (#760, #762) is currently admin-only. It moves to `response.annotate`, so Reviewers get it, which is the point of the role. Turning feedback on per form moves to `form.edit`.

### 3. Form-level scope

Each form has an **access mode**:
- `workspace` (default; every existing form): members use their workspace role on it, as today.
- `restricted`: only the **creator**, **Owner/Admins**, and **grantees** have access. Members see nothing else of it, not even in listings. The Privacy officer still sees its structure and its deletion requests, but no answers.
  - **Templates:** a template has no access mode and is visible to every member, so only an Owner, an Admin or the creator may save a restricted form as one (403 `template_from_restricted_form`; a Private form with no mode chosen counts as restricted). A grantee, even an Editor, cannot. Answers are never part of a template.

A **form grant** is `(form, principal, form role, export?)`:
- **Principal:** a user, or a **member group**.
- **Form role:** Editor, Reviewer or Viewer, with the content permissions of the workspace role of the same name, except that a grant never deletes the form (deleting drops its responses; it stays with workspace Editors, Admins and Owners). An Editor grant includes export; the `export` flag is for Reviewer and Viewer grants.
- **`export`:** optional. It adds `response.export` for Reviewers and Viewers on that form only.
- **Elevation:** a grant may give a member more on that form than their workspace role, so a Viewer can be Reviewer on the hiring forms. It never gives workspace-level permissions.
- **Who manages grants:** whoever has `form.share` on the form, within two caps. On a **restricted** form only Owners, Admins and the form's creator manage them, so a grantee who edits the form cannot widen who sees it:
  - **Grantor cap:** a grant can't give more on that form than the grantor holds there. An Editor can grant Editor, Reviewer or Viewer, but never workspace-level permissions.
  - **Export is reserved:** only the Owner and Admins can grant `export`. It is the bulk-data path, so it stays with the people accountable for the workspace.
- **Privacy officer is never elevated:** form grants don't apply to Privacy officers. A grant can never add `response.read`, `response.annotate`, `response.export` or `response.edit` to that role, so "never reads answers" holds on every form. A Privacy officer who also needs to review answers needs a different workspace role; that is an explicit choice, and it is visible in the members list.

**Member groups** are new and are not responder groups. They are named sets of workspace members, managed by hand or fed from SCIM groups; the product calls them **Teams** (the API says `member_groups`), and "groups" stays the respondent concept. Responder groups remain the "who may answer" mechanism. SCIM groups may later feed both, through separate mappings (not built).

Folders, and grants on folders, come later. The model already allows it: a folder grant is equivalent to a grant on every form in it.

### 4. API keys and MCP
- A key gets a **role** (Editor, Reviewer, Viewer or Privacy officer) and optionally a list of forms. It acts with exactly those permissions, never more than its creator may do **right now**: the creator's rights are looked up on every request, so a demoted creator shrinks the key on its next call. Built behind the server setting `API_KEY_ROLES_ENABLED` (off by default; limits already stored are enforced even when it is off). How the rights are worked out, the editing rules, the errors and how to roll back: [api-keys.md](api-keys.md).
- Keys belong to the workspace and admins see who created each one. When their creator is removed from the workspace, deletes their account or is deprovisioned by the directory, their keys are **revoked** (a key that only refused while its creator was gone would come back to life if the person were invited or provisioned again).
- Today's scopes map onto permissions: `forms:read` → `form.read`; `forms:write` → `form.edit`; `responses:read` → `response.read` **and** `response.export` (a bulk read through the API is an export); `deletion_requests:*` → `privacy.manage`.

- **A workspace that requires an authenticator app ([totp.md](totp.md)) does not cover API keys and MCP**, exactly as "require SSO" does not ([sso.md](sso.md)): they are machine credentials issued inside the workspace. A member without an authenticator app can still hold a key; closing that is the key-role step below, not the second factor.

### 5. SSO / SCIM mapping (Phases 1–3)
Status: SSO (Phase 1–2) and SCIM directory sync (Phase 3) are built ([sso.md](sso.md), "Directory sync"), and so is feeding Teams from directory groups (behind `FORM_ACCESS_ENABLED`).
- **Workspace roles:** IdP groups map to a workspace role (one per group; Admin allowed, never Owner). The highest role wins, and members with no mapped group get the workspace default (the SSO "role for new members", Viewer by default, never Owner). **Built.** Members the directory manages show "Managed by your directory" and their role can't be changed by hand (409 `managed_by_directory`); it follows their groups. Members invited by hand keep their role, and no owner's role is ever changed by the directory; an owner may still make a directory-managed member an owner. The directory still deactivates (and reactivates) a co-owner like any member; only the billing owner is never touched.
- **Member groups (Teams):** IdP groups feed Teams, which then carry form grants. For example, the IdP group "HR" is linked to the team "HR", which is Reviewer on the restricted hiring forms. **Built**, behind `FORM_ACCESS_ENABLED`: the **owner** links a directory group to a team (`PUT/DELETE /workspaces/{id}/scim/groups/{group_id}/team`, or the Teams tab). One IdP group is in at most one team, and a team may take several groups (a group can also map to a workspace role; the two mappings are independent). Who is in the team through a group is **read at call time** from the directory's tables (`scim_group_members` to `scim_users`), never copied, so there is no sync step and nothing can drift: deactivating or deleting someone in the directory, removing them from the group, or deleting the group takes them out of the team on the next request. A person counts only while their directory record is active and their membership in this workspace is enabled, and the link only ever reaches a team of the same workspace. A team can be fed by groups and listed by hand at once (the union; a person in both is one member); someone in only through a group is removed in the directory (409 `managed_by_directory` on a manual removal). Linking and unlinking are audited (`team_linked`, ids only), also when the directory deletes a linked group. With the switch off the two routes answer 422 `form_access_off` and the stored links decide nothing.
- **Deprovisioning:** **disables** the membership (rather than removing it, so it can be re-enabled and nothing is deleted) and revokes sessions. Forms the person created stay with the workspace. **Built**; a deprovisioned user's SSO sign-in is refused while the directory is connected.

## Enforcement
- One authorisation service, `authorize(user, permission, workspace_id, form_id=None)`, plus a listing filter for "forms this user can see". Services call these; controllers and repositories don't decide access.
- **Storage** (expand-only; Mongo collection plus Postgres twin each, following the persistence rules):
  - `workspace_users.roles` gains `EDITOR`, `REVIEWER`, `VIEWER`, `PRIVACY_OFFICER` and `OWNER`. An owner is `workspaces.owner_id` (the billing owner) or a membership holding `OWNER`, with an active membership either way. `COLLABORATOR` is read as `EDITOR`, and an Editor is still *stored* as `COLLABORATOR` (see step b below).
  - `workspace_forms.settings.access_mode`.
  - New tables `member_groups`, `member_group_members` and `form_access_grants` (revision `0037`, Postgres only, expand-only). Which directory group feeds a team is stored on the directory group (`scim_groups`, `member_group_id`), so one team can take several.
- **Webapp:** the backend returns the user's effective permissions for the workspace, and per form where relevant. The UI shows and hides controls from those permissions instead of `selectIsAdmin`, which today only means "is owner".
- **Respondent-facing paths are separate:** `/submissions/{id}` for the submitter, the submission-number receipt, My submissions, respondent feedback views, submitting and editing one's own response, and deletion requests by the submitter. These authorise by the submitter's identity or receipt, never through member permissions. A form's access mode therefore can't lock respondents out of their own submissions, and member grants never give anyone a respondent's view.
- **Tests:** a permission matrix test checks every endpoint × role × access mode against the tables above, including grants. It covers the grantor cap, export grants being reserved for Owner and Admins, and a Privacy officer with a grant still being refused answers. It is the regression net for future endpoints.

## Inconsistencies this replaces (from the current-code inventory)

Missing access checks are handled separately in a security fix. The inconsistencies below are resolved by the permission model:
- **Admin vs member mismatches:**
  - Members list needs admin, but the invitations list only needs membership.
  - Creating responder groups needs admin, but linking one to a form only needs membership.
  - The responders list needs membership, but its tags need admin.
- **AI insights vs raw responses:** AI insights (which read answers) need admin, while raw responses, CSV and MCP reads need only membership. Under the model they all become `response.read`, plus `response.export` for the bulk paths.
- **Member removal:** an admin can remove the owner, and removing a member used to delete the forms they created or imported. **Fixed:** the forms stay with the workspace (with or without form-level access) and are handed to the billing owner, in the same transaction as the removal and with one audit row per form; removing a member also removes their grants and team memberships.
- **"Hidden" forms:** they only affect listings, so they are not real access control. **Built** (behind `FORM_ACCESS_ENABLED`): while it is on, a form flagged Private with no access mode chosen counts as `restricted`, derived at read time with no data migration, so the creator, Owner and Admins have access, which is what users already believe "hidden" means. An explicit mode always wins. While it is off, `hidden` keeps its old meaning.
- **Search:** it always applies the non-member filter, even for members.
- **CSV export:** `GET /forms/{id}/export-csv` was broken (500). The CSV download moved behind `response.export` (see *Step b as implemented*, Export) and the broken route was removed (#771).

## Rollout (inside Phase 0)
| Step | Scope | Behaviour change |
|---|---|---|
| a | Permission catalogue + `authorize()`; every endpoint goes through it with today's semantics (Admin = admin, Collaborator = Editor) | none, apart from the fixed inconsistencies |
| b | New roles (Reviewer, Viewer, Privacy officer); role change endpoint and members UI; owner transfer | new roles only |
| c | Member groups, form grants, restricted access mode, listing filter; hidden → restricted migration | yes, for forms marked hidden (documented). **Built behind `FORM_ACCESS_ENABLED`** |
| d | Export permission across CSV, API/MCP and integrations; API keys get roles | keys default to their creator's role |
| e | Permission matrix test + effective permissions API for the webapp | none |

### Step b as implemented
- **Roles:** each role grants exactly its §2 column; a membership's permissions are the union over its roles. An empty role list (memberships from before roles existed, the schema default) is an Editor, as it always behaved. A role the code doesn't know grants nothing, and such a membership still loads (`roles` accepts unknown strings), so a later release's roles don't break this one.
- **Behaviour changes:** collaborators (Editors) lose `privacy.manage`: deletion requests, the responders list and its tags, the consent catalog and filing a deletion request for someone else move to Owner, Admin and Privacy officer. The consent catalog stays readable with `form.edit` (form builders pick from it). The workspace PATCH (name, handle, images, custom domain, policies) moves from owner-only to `workspace.manage`, so Admins can now change it.
- **Role change:** `PATCH /workspaces/{id}/members/{user_id}` `{role}` needs `members.manage`. One's own role is never changed, and no one gives a role with more permissions than their own, so only an owner gives `OWNER` (Admins can't promote anyone above Admin). Owners have their own rules (see *Owners*). Invitations take a role (Owner, Admin, Editor, Reviewer, Viewer, Privacy officer) and inviting again updates it. The members list reports each member's `role` (`OWNER` for every owner) and `billingOwner`.
- **Billing owner** (was "owner transfer"): see *Owners* below; `POST .../transfer-ownership` is now the old name of `POST .../make-billing-owner`.
- **Invitations:** carry a role and who sent them (`invited_by`). Inviting someone who is already a member is refused (409; change their role instead). Accepting re-checks the sender: if they no longer manage members or no longer hold every permission of the role, the invitation is refused. Invitations sent before step b have no sender and are not re-checked.
- **API keys and MCP:** every tool call also requires the key's creator to hold, right now, the permission its scope stands for (`forms:read` → `form.read`, `forms:write` → `form.edit`, `responses:read` → `response.read` **and** `response.export`, since reading responses through the API or MCP is an export, `deletion_requests:*` → `privacy.manage`); a removed, disabled or demoted creator makes the key refuse. Key roles stay step d.
- **Export:** the CSV download is `POST /workspaces/{id}/forms/{form_id}/exports` (`response.export`; streamed up to 5,000 responses, else a job with a short-lived signed link, an audit entry each: docs/response-export.md); `.../all-submissions` returns the decrypted, unpaginated responses, so it asks for `response.export` too. Attaching an action to a form (`POST .../forms/{form_id}/actions`) and turning one back on (`PATCH .../actions`, `enable`) need `response.export` as well as `form.edit`: an action runs on every submission and may send the answers out. Detaching or turning one off needs `form.edit` only. The "send me a copy" action (`creator_copy_mail`) may only mail a current, enabled member of the form's workspace (the form's creator only while they are still one; a removed or disabled creator receives nothing): any other `Receiving Mail Address` is refused with a 422 (`copy_recipient_not_allowed`) when it is attached, and the actions executor asks the backend again right before each mail (`POST /temporal/workspaces/{ws}/forms/{form}/copy-recipient`, in-network, key-protected), so a member removed or disabled since then receives nothing and the job fails with a message that names no address. Addresses are compared after trimming whitespace and case-folding; plus tags and dots are kept, so a member's `+tag` address counts only when it matches exactly. Every role with `form.edit` holds export today, so this matters only once a role has the one without the other. The flow view's insights read `GET /workspaces/{id}/forms/{form_id}/submission-paths` (`response.read`) instead: each submission's path through the pages (page ids, the jump taken out of each, the ending reached), replayed on the server against the form's current rules, with no answer values, identities, response ids or dates. The other bulk paths (API/MCP `responses:read`, integrations) are step d. The old `GET /forms/{id}/export-csv` answered 500 to everyone (it called a service method removed in 2024) and nothing called it, so it was removed rather than rebuilt (#771): the CSV was built in the browser from `.../all-submissions/export` until the server-side export replaced it (the rule moved to `services/response_export/table.py`, pinned by a test against the browser's old output; the Google Sheets action keeps its own formatting).
- **No data migration:** existing `COLLABORATOR` rows are not rewritten; `COLLABORATOR` stays the stored spelling of Editor indefinitely, and the API reports `EDITOR`. That needs no dual-store rewrite and keeps every existing membership and invitation readable by the previous release on a rollback. Memberships (`workspace_users.roles`) and invitations (`workspace_invites.role`) holding one of the new roles are **not** readable by a release before step b: its `WorkspaceRoles` enum refuses them when the document loads. On such a release that breaks `find_workspace_user` (every permission check for that member), `get_mine_workspaces` (their workspace list), `get_workspace_users` (the members list and accepting any invitation to that workspace), `disable_other_users_in_workspace` (the owner's downgrade) and, on Postgres, `enable_all_user_in_workspace` (the owner's upgrade), plus every read of such an invitation. So before rolling back, set those roles back to `COLLABORATOR` on memberships **and** pending invitations. This release itself loads unknown roles (memberships and invitations) and grants them nothing, so the next release's roles won't break it.

### Step c as implemented
Behind the server setting `FORM_ACCESS_ENABLED` (environment only, off by default). User-facing description: [form-access.md](form-access.md).
- **One decision.** `FormAccessService.permissions_on` is the only place that combines a member's workspace role, their grants (their own and through Teams) and the form's mode; `authorize()` calls it whenever a request names a form, and services never read grants. It is recomputed on every request (a revoked grant is effective on the next one; nothing is cached across requests) and remembered only within one request.
- **Off means unchanged.** With the switch off the decision returns the role's permissions at once, no grant or mode query is made, the routes that change teams, grants, the mode or directory links answer 422 `form_access_off`, and saved data stays. Turning it off while restricted forms exist re-opens them to every member's role.
- **Rules as built:** Owners and Admins always pass; the creator keeps their own role's rights on their form; a grant gives its role's form-scoped permissions and never the form's deletion; a Privacy officer is never elevated and, on a restricted form with no way in, keeps the structure and the privacy programme only; nothing is raised in a disabled workspace; single sign-on and authenticator-app blocks come first, so a grant never bypasses them.
- **Enforcement:** read paths (lists, search, counts, responses, analytics, the public API and MCP) and write paths (edit, publish, delete, automations, AI, operations) decide on the form. A member a restricted form is closed to gets the same "not found" as for a form that does not exist. Respondent-side paths are unchanged: restricting a form is about the team, not the respondent.
- **Audit:** access changes are written first (ids only) and refused when they cannot be recorded; see [form-access.md](form-access.md#the-audit-log).

### Owners (after step b)
A workspace can have **several owners with equal rights** (product decision, 2026-10-06): the person who pays is often not the person who sets up single sign-on, so the owner must be able to make their IT person an owner. Multiple Admins were already possible and are unchanged.
- **Storage:** an owner besides the billing owner is a membership with role `OWNER` in `workspace_users.roles` (both stores; expand-only, no data migration). `workspaces.owner_id` stays and remains an owner: it is the **billing owner**, the account whose plan and subscription the workspace runs on, and the anchor for code that needs one person (the personal/default workspace, plan upgrades and downgrades, the workspace limit). "Is an owner" = `owner_id` **or** an active membership holding `OWNER` (`is_owner_membership` in `models/enum/workspace_roles.py`; `AuthorizationService.is_owner`/`require_owner` go through `effective_permissions`, where only owners hold every permission).
- **Permissions:** every owner holds the whole Owner column, `workspace.billing` and the owner-only SSO and SCIM configuration included. In a disabled workspace (the billing owner's plan lapsed) every owner keeps the read and privacy permissions.
- **Making owners:** only an owner makes someone an owner (role change to `OWNER`, or an invitation with role `OWNER`; accepting re-checks that the sender is still an owner). Admins still can't promote above Admin.
- **Demoting and removing owners:** only an owner demotes or removes another owner. The billing owner can't be demoted or removed while they are the billing owner (403): another owner becomes the billing owner first. A workspace always keeps at least one active owner: a demotion or removal (leaving included) that would leave none is refused (409). Plan downgrades never disable owners, and the directory never touches the billing owner, so neither can leave a workspace without one.
- **The directory and SSO never grant or remove `OWNER`:** a group can't map to Owner, the SSO "role for new members" can't be Owner, and no owner's role is ever changed by it (owners are not counted as directory-managed). An owner may make a directory-managed member an owner by hand. **Deactivation still applies to co-owners:** when the IdP deactivates or deletes a co-owner (role `OWNER`), their membership is disabled (reason `directory`) and their sessions are revoked like any member's, so a person who left loses owner access, SSO sign-in and the break-glass at once; reactivation re-enables them with their stored role (still an owner). Only the **billing owner** is never touched (`owner_protected`), which keeps an active owner. Every owner with an active membership keeps the email-code break-glass while SSO is required, and their sessions are kept when "require SSO" signs members out.
- **Make billing owner:** `POST /workspaces/{id}/members/{user_id}/make-billing-owner` (`workspace.billing`, so any owner; the old `.../transfer-ownership` route does the same). The target must already be an active owner; the previous billing owner stays an owner. The previous billing owner's membership is given `OWNER` first, then `owner_id` changes in one conditional update (only while it is still the value read, `set_owner_if` in both stores), the target is checked again right after and the change undone if they stopped being an active owner. A failure at any point leaves an extra owner, never none; a membership change landing after the re-check is not caught. **Refused**, as before, for a personal (default) workspace and for one on a paid plan: the plan is the billing owner's (`User.plan`, their subscription), upgrades and downgrades find workspaces by `owner_id`, and sign-in recreates a personal workspace for an account that owns none. As billing stands, every non-default workspace is created on a paid plan, so the billing owner can in practice only change once plans are billed per workspace.
- **Billing stays per person:** Stripe customers, checkout and the customer portal are per account (`user_id`), never per workspace, so an owner only ever reaches their own Stripe data. A co-owner's own plan never changes a workspace they don't bill (upgrades and downgrades find workspaces by `owner_id`), and co-owned workspaces don't count toward their workspace limit. The webapp tells owners who are not the billing owner "Billing is handled by <billing owner>" instead of a billing link.
- **Deleting the workspace:** there is no endpoint that deletes a single workspace; workspaces are only deleted with their billing owner's account. **Deleting an account is refused** (409 `billing_owner_of_shared_workspaces`, naming each workspace) while the account is the billing owner of a workspace with another active owner (product decision, 2026-10-06). The way out: make another owner the billing owner, or remove the other owners; for a paid or personal workspace, whose billing owner can't change, only the latter (`billingOwnerCanChange: false`). Every path checks before deleting anything: the request (`POST /auth/user/delete/workflow`, before feedback is saved, the job is queued or any session ends), the deletion job (`AuthService.delete_user`, Temporal and procrastinate alike, before integrations, workspaces or the auth account) and `delete_workspaces_of_user_with_forms` itself. A co-owner deleting their account only loses their membership; the workspace stays.
- **Rollback:** a release before this one does not understand a membership holding `OWNER` as an owner: it loads it (that release already loads unknown roles) and treats it as a role granting nothing. On such a release every owner other than the billing owner (`owner_id`) loses all access, and a former billing owner who was made a co-owner by "make billing owner" (stored `OWNER`) loses theirs too. Nothing breaks and no data is lost; give those members `ADMIN` before rolling back if they need access meanwhile.
- **Rolling deploy:** while old and new pods serve side by side, an old pod does not know `OWNER`: an Admin served by it can demote or remove a co-owner (to that pod they are a member with an unknown role), and loading a pending invitation with role `OWNER` errors there. Keep the rollout short.

Rough size: a 3–4 days, b 3–4, c 5–7, d 2–3, e 2. That is **about 15–20 engineer-days**, which comes on top of the session-revocation and verified-domain parts of Phase 0 ([`docs/sso-spike.md` on the `spike/sso-polis` branch](https://github.com/bettercollected/bettercollected/blob/spike/sso-polis/docs/sso-spike.md)).

## Resolved questions (confirmed)
1. **Default role for SSO-provisioned members without a mapped group:** **Viewer**, configurable per workspace.
2. **Privacy officer and respondent emails:** a Privacy officer **can** see the respondent's email on a deletion request. Acting on the request needs the identifier, and that is not reading answers.
3. **Analytics on restricted forms:** members without a grant **cannot** see them; restricted means restricted.
4. **Admins opting out of seeing a restricted form:** **not in v1**; revisit later. The Owner and Admins remain the trust anchor, and the audit log records their access.
