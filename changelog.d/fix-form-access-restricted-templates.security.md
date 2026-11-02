- Saving a restricted form as a template is limited to Owners, Admins and the form's creator. A
  template has no access mode and is visible to every member of the workspace, so with form-level
  access on, a workspace Editor or a member with an Editor grant on a restricted form could copy
  its structure (never its answers) into the shared template library. They now get a 403
  `template_from_restricted_form`; a Private form with no access mode chosen counts as restricted.
  Open forms, and instances with form-level access off, behave as before.
