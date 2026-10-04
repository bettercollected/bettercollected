# Enterprise access model: roles, permissions and form-level scope

Status: **accepted** (2026-10-03; decisions and open questions confirmed by the product owner). Rollout: steps a and b are implemented (see *Rollout*); c to e are not. It is a prerequisite for SSO/SCIM, which is Phase 0 of the enterprise work in [`docs/sso-spike.md` on the `spike/sso-polis` branch](https://github.com/bettercollected/bettercollected/blob/spike/sso-polis/docs/sso-spike.md).

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
| `form.create` | create, import (Google/Typeform/PDF), from template |
| `form.read` | open a form in the dashboard (structure, settings) |
| `form.edit` | edit, publish, duplicate, settings, actions, responder-group links |
| `form.delete` | delete a form |
| `form.share` | form grants and access mode |
| `response.read` | individual answers (incl. AI insights, flow analytics per response) |
| `response.annotate` | internal fields, respondent feedback |
| `response.export` | CSV, API/MCP `responses:read`, integrations and actions that send responses out (sheets, webhooks, email copies) |
| `response.delete` | delete a response |
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
| response.delete | ✓ | ✓ | ✓ | | | |
| privacy.manage | ✓ | ✓ | | | | ✓ |
| analytics.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

- **Owner:** one per workspace. Ownership can be transferred but never removed, and no one can remove the owner.
- **Editor** is today's `COLLABORATOR`; existing collaborators migrate to Editor with no behaviour change. A new form is editable by its creator even inside restricted scopes.
- **Reviewer:** reads, annotates (internal fields) and responds to submissions (feedback), but does not change forms. This is the hiring and case-handling role.
- **Viewer:** read-only access to forms and their responses.
- **Privacy officer:** runs the privacy programme without reading answers. They handle deletion requests and see who the data subjects are (respondent identifiers, needed to act on a request). They manage consent, retention and privacy texts, and read the audit log. They cannot read answers, export, or change forms. They **complete** deletion requests: deleting a response that has a *pending* deletion request needs `privacy.manage` (or `response.delete`); any other delete needs `response.delete`. Combined with any other role on the same membership, a Privacy officer still never holds `response.read`, `response.annotate` or `response.export`. This role is deliberately unusual for a form tool and fits the trust-first positioning.

Respondent feedback (#760, #762) is currently admin-only. It moves to `response.annotate`, so Reviewers get it, which is the point of the role. Turning feedback on per form moves to `form.edit`.

### 3. Form-level scope

Each form has an **access mode**:
- `workspace` (default; every existing form): members use their workspace role on it, as today.
- `restricted`: only the **creator**, **Owner/Admins**, and **grantees** have access. Members see nothing else of it, not even in listings. The Privacy officer still sees its structure and its deletion requests, but no answers.

A **form grant** is `(form, principal, form role, export?)`:
- **Principal:** a user, or a **member group**.
- **Form role:** Editor, Reviewer or Viewer, with the content permissions of the workspace role of the same name.
- **`export`:** optional. It adds `response.export` for Reviewers and Viewers on that form only.
- **Elevation:** a grant may give a member more on that form than their workspace role, so a Viewer can be Reviewer on the hiring forms. It never gives workspace-level permissions.
- **Who manages grants:** whoever has `form.share` on the form, within two caps:
  - **Grantor cap:** a grant can't give more on that form than the grantor holds there. An Editor can grant Editor, Reviewer or Viewer, but never workspace-level permissions.
  - **Export is reserved:** only the Owner and Admins can grant `export`. It is the bulk-data path, so it stays with the people accountable for the workspace.
- **Privacy officer is never elevated:** form grants don't apply to Privacy officers. A grant can never add `response.read`, `response.annotate` or `response.export` to that role, so "never reads answers" holds on every form. A Privacy officer who also needs to review answers needs a different workspace role; that is an explicit choice, and it is visible in the members list.

**Member groups** are new and are not responder groups. They are named sets of workspace members, managed by hand or synced from SCIM. Responder groups remain the "who may answer" mechanism. SCIM groups may later feed both, through separate mappings.

Folders, and grants on folders, come later. The model already allows it: a folder grant is equivalent to a grant on every form in it.

### 4. API keys and MCP
- A key gets a **role** (Editor, Reviewer or Viewer) and optional form grants. It acts with exactly those permissions, never more than its creator had when it was created.
- Keys belong to the workspace, so removing their creator does not orphan them, but admins see who created each one.
- Today's scopes map onto permissions: `forms:read` → `form.read`; `forms:write` → `form.edit`; `responses:read` → `response.read` **and** `response.export` (a bulk read through the API is an export); `deletion_requests:*` → `privacy.manage`.

### 5. SSO / SCIM mapping (Phases 1–3)
Status: SSO (Phase 1–2) and SCIM directory sync (Phase 3) are built ([sso.md](sso.md), "Directory sync"); mapping to member groups waits for member groups (step c).
- **Workspace roles:** IdP groups map to a workspace role (one per group; Admin allowed, never Owner). The highest role wins, and members with no mapped group get the workspace default (the SSO "role for new members", Viewer by default). **Built.** Members the directory manages show "Managed by your directory" and their role can't be changed by hand (409 `managed_by_directory`); it follows their groups. Members invited by hand and the owner are never changed by the directory.
- **Member groups:** IdP groups map to member groups, which then carry form grants. For example, the IdP group "HR" becomes the member group "HR", which is Reviewer on the restricted hiring forms. **Not built** (needs member groups).
- **Deprovisioning:** **disables** the membership (rather than removing it, so it can be re-enabled and nothing is deleted) and revokes sessions. Forms the person created stay with the workspace. **Built**; a deprovisioned user's SSO sign-in is refused while the directory is connected.

## Enforcement
- One authorisation service, `authorize(user, permission, workspace_id, form_id=None)`, plus a listing filter for "forms this user can see". Services call these; controllers and repositories don't decide access.
- **Storage** (expand-only; Mongo collection plus Postgres twin each, following the persistence rules):
  - `workspace_users.roles` gains `EDITOR`, `REVIEWER`, `VIEWER` and `PRIVACY_OFFICER`. The owner is not a stored role: it is `workspaces.owner_id` with an active membership. `COLLABORATOR` is read as `EDITOR`, and an Editor is still *stored* as `COLLABORATOR` (see step b below).
  - `workspace_forms.settings.access_mode`.
  - New `form_access_grants` and `member_groups`.
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
- **Member removal:** an admin can remove the owner, and removing a member deletes forms they imported.
- **"Hidden" forms:** they only affect listings, so they are not real access control. They migrate to `restricted` with the creator, Owner and Admins having access, which is what users already believe "hidden" means.
- **Search:** it always applies the non-member filter, even for members.
- **CSV export:** `GET /forms/{id}/export-csv` is broken (500). It is rebuilt behind `response.export`.

## Rollout (inside Phase 0)
| Step | Scope | Behaviour change |
|---|---|---|
| a | Permission catalogue + `authorize()`; every endpoint goes through it with today's semantics (Admin = admin, Collaborator = Editor) | none, apart from the fixed inconsistencies |
| b | New roles (Reviewer, Viewer, Privacy officer); role change endpoint and members UI; owner transfer | new roles only |
| c | Member groups, form grants, restricted access mode, listing filter; hidden → restricted migration | yes, for forms marked hidden (documented) |
| d | Export permission across CSV, API/MCP and integrations; API keys get roles | keys default to their creator's role |
| e | Permission matrix test + effective permissions API for the webapp | none |

### Step b as implemented
- **Roles:** each role grants exactly its §2 column; a membership's permissions are the union over its roles. An empty role list (memberships from before roles existed, the schema default) is an Editor, as it always behaved. A role the code doesn't know grants nothing, and such a membership still loads (`roles` accepts unknown strings), so a later release's roles don't break this one.
- **Behaviour changes:** collaborators (Editors) lose `privacy.manage`: deletion requests, the responders list and its tags, the consent catalog and filing a deletion request for someone else move to Owner, Admin and Privacy officer. The consent catalog stays readable with `form.edit` (form builders pick from it). The workspace PATCH (name, handle, images, custom domain, policies) moves from owner-only to `workspace.manage`, so Admins can now change it.
- **Role change:** `PATCH /workspaces/{id}/members/{user_id}` `{role}` needs `members.manage`. The owner's role and one's own are never changed, and no one gives a role with more permissions than their own; `OWNER` is not a role (Admins can't promote anyone above Admin). Invitations take a role (Admin, Editor, Reviewer, Viewer, Privacy officer) and inviting again updates it. The members list reports each member's `role` (`OWNER` for the owner).
- **Owner transfer:** `POST /workspaces/{id}/members/{user_id}/transfer-ownership` needs `workspace.billing` (the owner). The new owner must be an active Admin; the old owner stays an Admin. `owner_id` changes in one conditional update (only while it is still the caller, `set_owner_if` in both stores), the target's membership is checked again right after and the change undone if they stopped being an active Admin, then the old owner is demoted. A failure in between never leaves the workspace without an owner; a membership change landing after the re-check is not caught (noted in the code). **Refused** for a personal (default) workspace and for one on a paid plan: the plan is the owner's (`User.plan`, their subscription), upgrades and downgrades find workspaces by `owner_id`, and sign-in recreates a personal workspace for an account that owns none. As billing stands, every non-default workspace is created on a paid plan (and disabled when the plan lapses), so transfer is in practice refused until plans are billed per workspace.
- **Invitations:** carry a role and who sent them (`invited_by`). Inviting someone who is already a member is refused (409; change their role instead). Accepting re-checks the sender: if they no longer manage members or no longer hold every permission of the role, the invitation is refused. Invitations sent before step b have no sender and are not re-checked.
- **API keys and MCP:** every tool call also requires the key's creator to hold, right now, the permission its scope stands for (`forms:read` → `form.read`, `forms:write` → `form.edit`, `responses:read` → `response.read` **and** `response.export`, since reading responses through the API or MCP is an export, `deletion_requests:*` → `privacy.manage`); a removed, disabled or demoted creator makes the key refuse. Key roles stay step d.
- **Export:** the CSV download reads `GET /workspaces/{id}/forms/{form_id}/all-submissions/export` (`response.export`); `.../all-submissions` stays `response.read` for the flow view's per-response insights. The other bulk paths (API/MCP `responses:read`, integrations) are step d. `GET /forms/{id}/export-csv` is still broken (500) and left alone.
- **No data migration:** existing `COLLABORATOR` rows are not rewritten; `COLLABORATOR` stays the stored spelling of Editor indefinitely, and the API reports `EDITOR`. That needs no dual-store rewrite and keeps every existing membership and invitation readable by the previous release on a rollback. Memberships (`workspace_users.roles`) and invitations (`workspace_invites.role`) holding one of the new roles are **not** readable by a release before step b: its `WorkspaceRoles` enum refuses them when the document loads. On such a release that breaks `find_workspace_user` (every permission check for that member), `get_mine_workspaces` (their workspace list), `get_workspace_users` (the members list and accepting any invitation to that workspace), `disable_other_users_in_workspace` (the owner's downgrade) and, on Postgres, `enable_all_user_in_workspace` (the owner's upgrade), plus every read of such an invitation. So before rolling back, set those roles back to `COLLABORATOR` on memberships **and** pending invitations. This release itself loads unknown roles (memberships and invitations) and grants them nothing, so the next release's roles won't break it.

Rough size: a 3–4 days, b 3–4, c 5–7, d 2–3, e 2. That is **about 15–20 engineer-days**, which comes on top of the session-revocation and verified-domain parts of Phase 0 ([`docs/sso-spike.md` on the `spike/sso-polis` branch](https://github.com/bettercollected/bettercollected/blob/spike/sso-polis/docs/sso-spike.md)).

## Resolved questions (confirmed)
1. **Default role for SSO-provisioned members without a mapped group:** **Viewer**, configurable per workspace.
2. **Privacy officer and respondent emails:** a Privacy officer **can** see the respondent's email on a deletion request. Acting on the request needs the identifier, and that is not reading answers.
3. **Analytics on restricted forms:** members without a grant **cannot** see them; restricted means restricted.
4. **Admins opting out of seeing a restricted form:** **not in v1**; revisit later. The Owner and Admins remain the trust anchor, and the audit log records their access.
