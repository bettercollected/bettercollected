- API keys can no longer tell a closed form from a missing one. With form-level access on, the public API
  answered a form closed to the key's creator with the 404 of an unknown form, but a missing form
  only after the request's input had been checked, so a bad query or body (`page=0`, an invalid
  JSON body) gave a different answer for the two, and a bad submission body spent the form's
  submission budget for a missing form only. A missing form now answers exactly as a closed one,
  before any input is read and before a budget is spent. A response of the public API is also
  decided on its form before it is decrypted, so nothing is decrypted for a response outside the
  key's reach.
