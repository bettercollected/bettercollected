- The groundwork for limiting a workspace API key to a role (Editor, Reviewer, Viewer or Privacy
  officer) and to a list of forms, behind `API_KEY_ROLES_ENABLED` (off by default, read from the
  environment only; while it is off, every key behaves exactly as before and no query is added).
  A key acts as the person who made it, narrowed: what it may do on a form is what its creator may
  do there right now, intersected with its role's permissions and, for a key limited to a list of
  forms, with its entry for that form, so it never does more than its creator and never more
  after the creator is demoted or removed. A form outside a limited key's list answers exactly as
  a form that does not exist. Nothing sets a role or a list yet; limits that are stored on a key
  are enforced even with the switch off, so turning it off never widens a key.
  The people and teams a form is shared with, and who may change that, never include a key's entry.
