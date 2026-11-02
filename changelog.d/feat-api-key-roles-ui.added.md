- The API keys page (AI, MCP tab) can now give a key a role (Editor, Reviewer, Viewer or Privacy
  officer, or the same as its creator) and limit it to a list of forms, and an Edit button changes a
  key's name, role and forms later (never its scopes). A new key starts on the lowest role that allows
  the scopes ticked. A combination the server would refuse (a role that cannot carry a scope, a list
  with "Delete forms" or a deletion-request scope) is explained on the page before anything is sent.
  Editing in a way that gives the key more reach (a higher role, every form in place of a list, more
  forms, a cleared role) shows a warning first and its button reads "Widen and save"; when somebody
  else changed the key meanwhile the dialog offers to reload it and try again. Each key in the list
  shows its role and "All forms" or the number of forms (the titles on demand), and a reminder counts
  the keys that still follow their creator's role. Every refusal the key routes can give has a message
  in English and Dutch. All of it shows only while the server has `API_KEY_ROLES_ENABLED` on (told with
  the workspace permissions as `apiKeyRolesEnabled`): with it off the page is as it was, asks for no
  extra data, and only a key that already stores a role or a list shows it, read only.
