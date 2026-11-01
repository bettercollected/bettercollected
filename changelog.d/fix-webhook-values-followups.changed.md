- Webhook and registration bodies are stricter about what a mapped answer may hold. A `date`, day
  or time answer stored as an empty string is now sent as `null` (it was `""`), and a part that
  is not in its published format goes out as `null`: a date that is not a calendar date, a time
  that is not `HH:MM`, a currency code that is not three capital letters, an amount that is not a
  plain decimal or is longer than any question allows, and a date range that ends before it
  starts. This also covers answers that logic hid or a jump skipped, which are stored as they
  came. A tags answer is cut to 30 tags of 1 to 40 characters, as the question itself allows.
  The body's `values_schema` says the same (`maxItems`, `maxLength`). Receivers of live
  webhooks may see `null` where they saw an empty string or an odd value.
