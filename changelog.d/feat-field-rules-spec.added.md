- Field rules through the API: the operation `set_field_rules` sets the rules
  of a question (public API, MCP `update_form`, and the AI assistant while
  field rules are on), and `validate` warns about rules while they are off.
  Every write path, the new operation included, holds the
  `FIELD_RULES_ENABLED` setting, which stays off by default.
