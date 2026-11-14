- Automatic spam check (`CAPTCHA_ENABLED`, off by default) now also guards the mails the
  public can trigger: the sign-in code of a respondent and of a creator, and the link of a
  saved draft. The browser solves the same small calculation (purpose `mail`, a bit harder:
  18 bits, `API_CAPTCHA_BASE_BITS_MAIL`) before the code or link is requested; the proof is
  bound to its purpose, workspace and form, so a proof for a submit is no good for a mail and
  the other way round. It is checked before the per-address and per-client limits count, so a
  request without a proof uses up nobody's budget. The page asks for it only when the server
  does: with the switch off nothing changes.
- Workspace owners and admins can set the spam check on or off by default for the forms of a
  workspace (Workspace, Spam protection; a form's own setting still wins). Each form's settings
  and that page show how many proofs passed and were blocked in the last 30 days (counts by day
  in the new `captcha_daily_counts` table, migration 0041; no address, network or person is
  stored), and changes to the setting are recorded in the activity log. See `docs/captcha.md`.
