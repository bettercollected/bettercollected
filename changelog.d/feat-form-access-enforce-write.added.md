- Form-level access is now enforced wherever a form is changed, behind `FORM_ACCESS_ENABLED` (off by
  default; while it is off nothing is decided differently and no query is added). With it on, editing,
  publishing, deleting and duplicating a form, its settings and responder groups, its automations
  (actions, webhooks, email actions, registration), the AI chat, review and insights, the operations
  API, version restore, the Open Formulieren export and creating a template from a form all decide on
  that form: a member a restricted form is closed to gets the same "not found" as for a form that does
  not exist (a permission their role lacks stays the usual "forbidden"). A grant gives what its role
  gives and never deletes the form; owners and admins always pass. A copy of a restricted form is
  restricted too. The delivery logs of a restricted form are for whoever may edit it (the audit log
  permission alone no longer opens them), and the workspace figure for deletion requests counts the
  forms a Privacy officer may handle.
