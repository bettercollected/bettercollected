# Who can open a form: restricted forms, grants and Teams

For workspace owners and admins. It explains how to decide, form by form, which members of your workspace can open a form in the dashboard, and what that does and does not change.

It is a feature of the server, and it is **off until whoever runs the server turns it on** (see [The switch](#the-switch-and-what-off-means)). While it is off, none of this exists for your workspace: every member opens forms as their role allows, exactly as before.

## In short

- Every member already has a **role** (Owner, Admin, Editor, Reviewer, Viewer, Privacy officer). By default a role applies to **every form** in the workspace.
- A form can be made **restricted**. Then only owners, admins, the person who created the form and the people and teams you add can open it. Everyone else in the workspace behaves as if the form does not exist: it is not in their lists, not in their search, not in their counts, and its address answers "not found".
- You can also give a person or a **team** extra access on **one form** without changing their role, for example making a Viewer a Reviewer on the hiring forms only. That is a **grant**.
- A **team** is a named group of your members. A grant to a team reaches everyone in it, so you manage a group once instead of form by form. A team can be filled by hand, or fed by a group of your company directory.
- None of this changes who can **fill in** a form. That is decided by the form's visibility for respondents, which stays separate (see [Respondents are a separate question](#respondents-are-a-separate-question)).

## Restricted forms

Open a form, then **Settings, Access**. The card "Who on your team can open this form" has two choices:

| Choice | Who can open the form |
|---|---|
| Everyone in the workspace, by their role | Every member, as far as their role allows. This is how every form works today. |
| Only selected people and teams | Owners, admins, the form's creator, and the people and teams listed on the card. |

- Switching in either direction asks for a confirmation. Restricting shows how many people will lose access first.
- Owners and admins always keep access to every form, restricted or not. They cannot be locked out of a form, and they cannot opt out of seeing one. Their reading of response data is recorded where it already was (exports, response history); see [The audit log](#the-audit-log).
- The creator keeps what their own role allows on their own form, nothing more. If they are later demoted, they keep only what the lower role gives. If they leave the workspace, the rule stops applying to them.
- A restricted form with nobody added is still open to owners, admins and its creator.
- A copy of a restricted form (duplicate) is restricted too.
- A restricted form can be saved as a workspace template only by an owner, an admin or its creator, because every member can see a template. Answers are never part of a template.
- Who changes the mode, and who edits the list: on a **restricted** form only owners, admins and the creator. A member who was given an Editor grant on it can edit the form and read its answers, but cannot widen who has access. On a form that is open to the workspace, anyone who may share the form can add people, within the limits below.

### Private forms from before

Forms marked **Private** in the form's visibility settings (the old way to hide a form from other members' lists) count as restricted while this feature is on, until someone chooses a mode on the Access card. What changes the day it is switched on:

- Owners and admins now see Private forms in lists, and every other member no longer reaches them anywhere, including the places that used to admit any member who knew the address.
- The old rule "the creator sees it in the list" becomes "the creator keeps access", as for any restricted form.
- Choosing a mode on the Access card replaces this guess for that form from then on.

## Grants

A grant gives one person or one team a role **on one form**. The roles have the same content rights as the workspace role of the same name:

| On this form | Editor | Reviewer | Viewer |
|---|---|---|---|
| Open the form and its structure | yes | yes | yes |
| See answers and the form's statistics | yes | yes | yes |
| Add internal notes and respond to submissions | yes | yes | no |
| Edit, publish and share the form | yes | no | no |
| Delete or edit answers | yes | no | no |
| Export answers | yes | only if allowed | only if allowed |

- A grant **adds** to a person's role on that form; it never removes anything a role gives. Demoting someone does not remove their grants.
- A grant never gives workspace-level rights (members, billing, security, settings), and never deletes the form itself: that stays with the workspace's Editors, admins and owners.
- **Exporting** is its own tick box, "May export responses", on Reviewer and Viewer grants. Only owners and admins can set it, because an export is how data leaves the product in bulk. An Editor grant includes export.
- **You can only give a role that is no higher than your own on that form.** An Editor on the form can give Editor, Reviewer or Viewer. A Reviewer cannot give access at all.
- Nobody changes their own access to a form.
- A **Privacy officer** is never given a grant (see [below](#what-a-privacy-officer-sees)); the server refuses it, because it would do nothing.
- A person in several places (a grant of their own and two teams) holds the union of what they give.
- A grant to someone whose membership is deactivated does nothing until they are active again; the card shows "This person is deactivated".

The card lists who was given access, with the role, who gave it and when. Removing a grant takes away the extra access only; the person keeps whatever their workspace role allows.

## Teams

**Workspace, Members, Teams.** Owners and admins create, rename and delete teams and choose their members.

- A workspace can have **20 teams** and a team **500 members listed by hand**. Names are unique in the workspace, ignoring capitals and extra spaces.
- Only **active** members can be added.
- Deleting a team deletes the grants that named it (the confirmation says on how many forms), and unlinks any directory groups feeding it.
- Teams are not the "groups" of the form's respondent settings. Those decide who may fill in a form; teams decide who may open it in the dashboard.
- On the Members page, **What can they open?** in a member's menu shows their teams and the grants they hold on single forms.

### Directory groups feeding a team

If your workspace has a directory connected ([directory sync, in single sign-on](sso.md#directory-sync-scim)), the **owner** can link a directory group to a team under **Teams, Linked directory groups**. Then:

- The people in that group in your directory are in the team. It is **read each time access is checked, never copied**, so there is nothing to keep in step. Take someone out of the group, deactivate them, or delete them in your directory, and their team access ends on their next request.
- **One directory group is in one team.** Linking a group to another team moves it. **One team can take several groups.** A person in two of them, or also listed by hand, is one member.
- Someone who is in a team only through a directory group is removed in the directory, not on the team page (the page says "From your directory" and refuses a manual removal).
- Unlinking, or deleting the team, takes the group's people out of the team. Nobody is deleted and the team keeps its other members and its grants.
- If the directory deletes the group, the link ends the same way.
- Only the owner links and unlinks, like the other directory settings, and only the owner sees this section.
- A directory group only feeds a team **of the same workspace**. It does not touch the workspace roles the same group may also map to (a group can do both).

## Who can do what

| | Owner | Admin | Editor | Reviewer | Viewer | Privacy officer |
|---|---|---|---|---|---|---|
| Open any form, restricted or not | yes | yes | open forms; restricted only if creator or granted | open forms; restricted only if granted | open forms; restricted only if granted | form structure only, see below |
| Make a form restricted, or open it again | yes | yes | only their own forms | no | no | no |
| Add or remove access on a restricted form | yes | yes | only on their own forms | no | no | no |
| Add or remove access on an open form | yes | yes | yes, within their own role on it | no | no | no |
| Allow exporting on a grant | yes | yes | no | no | no | no |
| Create, edit and delete teams | yes | yes | no | no | no | no |
| Link a directory group to a team | yes | no | no | no | no | no |
| Turn the feature on or off | whoever runs the server; not a workspace setting | | | | | |

A member who is closed out of a form is told the same thing as for a form that does not exist, so a restricted form's existence is not given away. A member who can open a form but lacks one permission on it gets the usual "not allowed".

## What a Privacy officer sees

The Privacy officer role exists so someone can run the privacy programme **without reading answers**. Form-level access keeps that true everywhere:

- Grants **never apply** to a Privacy officer. They cannot be added to a form's access list, and a team grant gives them nothing, so no form can turn them into someone who reads answers.
- On an open form they see what the role always gave: the form's structure, its statistics, deletion requests, the data subjects list, consent, retention and privacy texts, and the audit log. No answers, no export, no edits.
- On a **restricted** form they still see the form's structure and its deletion requests, because a deletion request has to be answerable. They see no answers and no statistics, and the form shows the "Restricted" chip in their list.
- They can read the [audit log](#the-audit-log), including every access change. It shows who changed access to which form, never an answer.

If someone has to read answers as well, give them a different workspace role. That is an explicit choice, and it shows in the members list.

## Respondents are a separate question

There are two independent questions about a form:

1. **Who on your team can open it in the dashboard?** Decided on the Access card, described above.
2. **Who can fill it in?** Decided by the form's visibility for respondents: Public, Private (only you) or only certain respondent groups.

They combine like this:

| Team access | Respondent visibility | Result |
|---|---|---|
| Everyone, by role | Public | As before. |
| Only selected | Public | The public can fill it in; only the selected people and owners and admins can open its answers. This is the usual choice for a hiring or complaints form. |
| Only selected | Private or certain groups | Respondents follow the respondent rule; the team follows the Access card. Two separate decisions. |

A restricted form never locks a respondent out of the form, their own submissions or their receipt. A member who is closed out of a form is treated, on the respondent side, like any other signed-in person: they see what a respondent would see, never the dashboard view.

The one place the two meet is the old **Private** flag, described above.

## API keys and the assistant

A workspace API key (and the MCP server) acts **as the person who created it**. The key of an owner or an admin reaches every form, restricted ones included. The key of someone a restricted form is closed to gets the same "not found" as that person. What a grant gives a member, their key gives too.

## The audit log

Every change to access is written to the workspace's audit log **before** it is made, with who, when and ids only (the form, the team, the person, the role, the export flag, the new mode, a count). Never a team's name, a form's title or an address. If the entry cannot be stored, the change is refused and nothing happens ("The change could not be recorded, so it was not made").

| Entry | When |
|---|---|
| `access_grant_added`, `access_grant_changed`, `access_grant_removed` | A grant on a form |
| `access_mode_changed` | A form was restricted or opened |
| `team_created`, `team_renamed`, `team_deleted` | A team |
| `team_member_added`, `team_member_removed` | A person listed by hand |
| `team_linked` | A directory group was linked to a team or unlinked from it (`linked` says which; also when the directory deletes a linked group) |
| `access_member_purged` | A person who left the workspace or deleted their account had N grants and team memberships removed |
| `form_creator_reassigned` | A removed member's forms were handed to the workspace's billing owner |

Owners, admins and Privacy officers can read the audit log (`audit.read`): the workspace's activity, and the activity of one form, through the routes described in [audit-log.md](audit-log.md) (they are behind their own switch, `AUDIT_LOG_UI_ENABLED`). Entries are recorded whether or not that page is on, and are kept as long as the workspace's other audit entries.

## When people leave

| Event | What happens to their access |
|---|---|
| Removed from the workspace | Their own grants and manual team memberships are deleted, and one entry records how many. Forms they created are **kept** by the workspace and handed to the billing owner. |
| Deactivated (plan limits, or deactivated in your directory) | Nothing is deleted. The grants do nothing while the membership is off, and work again if it is switched back on. A person in a team through a directory group is out of it immediately. |
| Deleted their account | As removed, in every workspace they belonged to. |
| Role changed | Grants are untouched; the person holds the union of the new role and the grants. |
| A form is deleted | Its grants go with it. |
| A team is deleted | Its grants go with it, and its directory links are removed. |
| A team has no members | Nothing changes: the grant stays, the card shows "Team has no members". A restricted form nobody was added to is still open to owners, admins and its creator. |

## The switch and what "off" means

Access per form is controlled by the server setting **`FORM_ACCESS_ENABLED`**. It is **off by default**, it is read from the server's environment (it is not in the admin portal), and it is not a per-workspace setting: whoever runs the server turns it on for everyone.

**On:** restricted forms, grants and teams are enforced on every request that names a form, in the dashboard, the public API and the MCP server. The Access card, the Teams tab and the "Restricted" chip appear.

**Off** (the default):

- Nothing is enforced. Every member opens forms as their workspace role allows, as before, and the server does no extra work to decide it.
- The Access card, the Teams tab and the chip are hidden.
- The routes that change teams, grants, modes or directory links answer **422 `form_access_off`** and write nothing. (Reading a form's access answers `enabled: false`.)
- **What you saved stays**: grants, teams, team members, each form's mode and directory links. Turning it back on applies them all at once.
- **Private forms** go back to their old meaning: hidden from other members' lists, with the endpoints open to any member who knows the address.

**Turning it off while restricted forms exist re-opens them to every member's role.** Turning grants off only removes extra access; turning restricted forms off removes protection. If you rely on a restricted form to keep people out, do not switch the feature off without first deciding what should happen to those forms.

Removing a member keeping their forms with the workspace, and removing their grants when they leave, do not depend on the switch.

## Routes

Everything is under `/api/v1/workspaces/{workspace_id}`, for a signed-in member of the workspace. Every route but the first answers 422 `form_access_off` while the feature is off. A form, team, member, grant or directory group of another workspace is a 404, the same as one that does not exist.

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/forms/{form_id}/access` | `form.read` | The mode, whether it is restricted, what the caller may do on the form, and (for whoever may share the form) the list of grants. `{enabled: false}` while off. |
| GET | `/forms/{form_id}/access/candidates` | who may share the form | People (id, name) and teams (id, name, size) that could be added. |
| GET | `/forms/{form_id}/access/impact?mode=restricted` | who may share the form | A dry run: how many members would lose access. Nothing is changed or recorded. |
| PUT | `/forms/{form_id}/access/mode` | `form.share` and the rule above | `{mode: "workspace" \| "restricted"}`. Audited. |
| PUT | `/forms/{form_id}/grants` | `form.share` and the caps above | `{subjectType: "user" \| "group", subjectId, role: "EDITOR" \| "REVIEWER" \| "VIEWER", export}`. Adds or replaces the grant for that person or team. 403 `access_manage_forbidden`, `grant_above_own_role`, `export_grant_reserved`, `cannot_grant_self`; 422 `privacy_officer_cannot_be_granted`. |
| DELETE | `/forms/{form_id}/grants/{grant_id}` | `form.share` and the rules above | 204. |
| GET, POST | `/member-groups` | `members.manage` | List; create `{name, description?}`. 409 `team_name_taken`, `too_many_teams`. |
| GET, PATCH, DELETE | `/member-groups/{team_id}` | `members.manage` | A team with its members (`viaDirectory` marks those who are in through a directory group), how many forms it is used on and how many directory groups feed it; rename; delete. |
| PUT, DELETE | `/member-groups/{team_id}/members/{member_id}` | `members.manage` | Add or remove a person listed by hand. 409 `team_full`; 409 `managed_by_directory` for a person who is in only through a directory group. |
| GET | `/members/{member_id}/access` | `members.manage` | A person's teams and grants, with the title of each form the caller may open. |
| PUT | `/scim/groups/{group_id}/team` | Owner | `{teamId}`: the directory group's people are in that team. 404 for a group or team that is not this workspace's. Linking a group that is linked elsewhere moves it. |
| DELETE | `/scim/groups/{group_id}/team` | Owner | Unlinks the group. |

`GET /workspaces/{workspace_id}/permissions` also reports `formAccessEnabled`. The dashboard lists, search and a form's own read carry an `access` block describing the reader's own view of each form. The directory overview (`GET .../scim`) names the team of each group (`teamId`).

The public API (`/api/v1` with a key) has no routes of its own for this. It applies the same decision to every form route a key calls; see [API keys and the assistant](#api-keys-and-the-assistant).
