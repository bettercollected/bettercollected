- Creating an API key can now set a role (Editor, Reviewer, Viewer or Privacy officer) and limit the
  key to a list of forms, and a new edit route changes a key's name, role and forms later (never its
  scopes, its creator or its secret). Both are behind `API_KEY_ROLES_ENABLED` (off by default):
  while it is off, setting a role or a list answers 422 `api_key_roles_off` and every key behaves
  exactly as before. A role must be able to carry the key's scopes, and a key limited to forms never
  carries `forms:delete` or the deletion-request scopes; a key never gets a role above the person who
  makes it. Owners and Admins may widen a key in place, and the audit log records it as a widening.
  The keys list shows each key's role and forms (the form titles only where the reader may open the
  form), and the workspace permissions say whether key roles are on (`apiKeyRolesEnabled`).
- Creating, changing and revoking an API key from the API keys page is now recorded in the
  workspace's audit log (key id, role, form scope and the forms added or removed; never a key's name,
  prefix or token), before the change is made.
