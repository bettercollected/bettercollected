- `python -m backend.migrate_builtins` (`preflight`, `apply`, `verify`, `rollback`) moves a form's
  built-in actions onto the backend's own features: "send a webhook", Slack and Discord become webhooks,
  "send me a copy" and the respondent's copy become email actions, and the Google Sheets action is run
  by the backend. Nothing is sent and no switch is turned on; what cannot move (an address that is not
  public https, a recipient who is not a member, a full limit, a switch that is off) is reported and
  left as it is. The old action is switched off in the same step, and `rollback` gives it back. The
  moved webhooks and email actions appear in the Webhooks and Email actions panels.
