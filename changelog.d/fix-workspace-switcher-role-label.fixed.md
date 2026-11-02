- The workspace switcher now shows your actual role in each workspace (Owner, Admin, Editor, Reviewer,
  Viewer or Privacy officer, in English and Dutch). It labelled everyone who is not an owner
  "Collaborator". When a role is not known, no label is shown. `GET /workspaces/mine` now reports
  the caller's `role` per workspace.
