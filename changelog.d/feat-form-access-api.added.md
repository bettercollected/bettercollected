- Teams and grants on a form, as API routes (behind `FORM_ACCESS_ENABLED`, off by default; every
  route but the read of a form's access answers 422 `form_access_off` while it is off, and no
  screen shows them yet): teams of workspace members (`/workspaces/{id}/member-groups`, owners
  and admins), the people and teams a form is shared with (`PUT/DELETE .../forms/{id}/grants`)
  and a form's access mode (`PUT .../forms/{id}/access/mode`). A role given on a form is never
  above the giver's own, only an owner or admin allows exporting responses, nobody changes their
  own access, a privacy officer is never given one, and on a restricted form only an owner, an
  admin or the form's creator decide who may open it. Every such change is written to the
  workspace's audit log first (ids only) and is refused when it cannot be recorded. Deleting a
  form, a team, a member or an account removes the grants and team memberships that named it.
  `GET /workspaces/{id}/permissions` also reports `formAccessEnabled`.
  Until the feature is released the switch is read from the environment only (the admin portal's settings
  do not offer it).
