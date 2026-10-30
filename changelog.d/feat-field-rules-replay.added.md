- Field rules: a question can now carry rules that require it or make it
  optional, make it read-only, set its value (a fixed value or a formula), or
  change its title or description while a condition or formula holds. The
  server replays them on every submission and response edit: it enforces
  Required with the rules applied, computes set values itself and discards
  what a respondent sent for a read-only question. Rules are part of form
  spec v1 (`rules` on a question) and are checked whenever a form is saved.
  Creating or changing rules is off until the new server setting
  `FIELD_RULES_ENABLED` is turned on (saves that bring new or changed rules
  answer 422 `field_rules_disabled`); no editor creates rules yet.
