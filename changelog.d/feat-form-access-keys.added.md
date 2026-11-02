- Form-level access now covers workspace API keys, in the public API and in the MCP server, behind
  `FORM_ACCESS_ENABLED` (off by default; while it is off nothing is decided differently and no
  query is added). A key acts as the person who made it: the key of an owner or an admin reaches
  every form, restricted ones included, and the key of a member a restricted form is closed to
  (an editor since demoted, say) gets the same "not found" as for a form that does not exist, on
  every form route (read, replace, publish, delete, operations, responses, deletion requests, and
  creating or changing a response through the submissions API) and in every MCP tool that names a
  form or a response. What a grant gives that member, the key gives; a form the key can open
  but not use for a call is the usual 403. Respondent-side submissions through the submissions API
  are unchanged: restricting a form is about the team, not the respondent.
