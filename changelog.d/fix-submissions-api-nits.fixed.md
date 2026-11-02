- Submissions API: a key that may not write to a form no longer uses up that form's per-window
  write budget; `consentItems` naming an unknown id is refused (422 `unknown_consent_item`) also on
  a form with no consent items; and a write that is finishing after its client disconnected can no
  longer be dropped before its idempotency key is finished. The API key dialog's "Only for these
  forms" list now reaches every published form (it stopped at 100).
