- Form-level access (behind `FORM_ACCESS_ENABLED`, off by default; with it off no payload and no
  query changes): the dashboard's forms list, search and a form's own read carry an `access`
  block with the reader's own view (`restricted`, `canManage`, `permissions`), read once for the
  whole page. `GET /workspaces/{id}/members/{user}/access` names the form (`formId`, `formTitle`)
  of each grant, only for forms the caller may open. Whoever may change a form's circle but cannot
  list the members (an Editor who created it) gets a name-only picker, `GET
  .../forms/{id}/access/candidates` (people and teams with their size; no addresses, nothing
  audited). A team grant reports the team's `memberCount`, a grant its giver's name (`grantedBy`),
  and `GET .../forms/{id}/access/impact?mode=restricted` counts, as a dry run, the members who
  would lose access if the form were restricted.
