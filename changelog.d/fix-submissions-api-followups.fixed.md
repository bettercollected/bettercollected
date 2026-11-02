- Submitting responses through the API now records consent as it was asserted: `"consent": true`
  accepts the form's required consent items only, and an optional item is accepted only when its id
  is named in the new `consentItems` (an unknown id is refused, an unnamed optional item is stored as
  not accepted); the SDKs take `consent_items` / `consentItems` and the command line `--consent-item`.
  A response with an open deletion request takes no update from a key (409 `deletion_requested`). A
  client that disconnects after a write started no longer frees its `Idempotency-Key`. One form takes
  at most 60 submissions a minute through the API. The documentation now says that the form's own
  email actions, webhooks and actions still run for a key's submissions.
