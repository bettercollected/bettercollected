- An API key limited to a list of forms can no longer create a form: it could not open what it
  made, and adding the new form to its own list would be a widening made by a secret instead of
  by an admin. The public API's `POST /forms` and the MCP tools `create_form`,
  `create_form_with_ai`, `create_form_outline` and `build_form_from_outline` answer 403
  `key_form_scope` for such a key (a refused MCP call is recorded in the API audit log). The
  refusal also applies when `API_KEY_ROLES_ENABLED` has been switched off since the limit was
  set. The OpenAPI document and the SDK types describe the new answer, and the `bettercollected`
  command line tool tells the user to ask an admin for another key when `create` or `promote`
  is refused for this reason.
