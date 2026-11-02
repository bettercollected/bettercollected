- Form-level access is now enforced wherever a form or its answers are read, behind
  `FORM_ACCESS_ENABLED` (off by default; while it is off nothing is decided differently and no
  query is added). With it on, a member a restricted form is closed to gets the same "not found"
  as for a form that does not exist, and the form is left out of the dashboard list, the search,
  the workspace counts, the all-submissions and responders views, the analytics of its page
  and the form lists of the MCP server and the public API, narrowed before anything is counted or
  paged. Owners and admins always see every form; a member with a grant sees what the grant gives.
  A form restricted against a member is still offered in the public list as to any respondent when
  it is open to respondents, and a member still reads their own submission of it. Email "team
  recipients" and "send me a copy" never send the answers of a form to a member who may not read
  them.
