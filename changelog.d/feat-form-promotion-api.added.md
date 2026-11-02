- A form's structure can be copied to another workspace as a draft, behind `FORM_PROMOTION_ENABLED` (off by
  default, environment only; the routes answer 422 `form_promotion_disabled` while off). `POST
  /workspaces/{id}/forms/{form_id}/promotion/preview` shows the diff, what is adjusted and what is not copied
  (counts only), and `.../promotion/apply` writes a new draft or the draft of an existing form, with the
  source's and target's ETags (412 when either changed) and an `Idempotency-Key`. Both sides are checked for the
  same person (`form.read` on the source, `form.create` or `form.edit` in the target, a target workspace you are
  not in answers 404); a restricted form is copied only by an Owner, an Admin or its creator and stays
  restricted. An existing target keeps its retention, purpose and privacy link unless you tick to copy them.
  Option lists are matched by name, answer-fed options are dropped, answers, webhooks, email actions, connected
  actions and case system hand-overs never move. `GET .../promotion/targets` lists the forms to update and
  `GET .../spec-file` downloads the form's document. Both sides are recorded in the Activity log
  (`form_copied_out`, `form_promoted`) before anything is written. Adds `formPromotionEnabled` to the workspace
  permissions. See `docs/environments.md`.
