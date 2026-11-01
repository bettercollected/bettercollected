- An address question: street, house number, an optional addition, postcode, city and country
  (the Netherlands by default, other countries when the creator allows them). The server checks
  every answer (Dutch postcodes as `1234 AB`, Dutch house numbers, the allowed countries), the
  public API, the MCP server and both SDKs carry it, logic conditions compare its postcode, the
  CSV export writes it as one line, and the AI never reads it. It is behind
  `ADDRESS_QUESTION_ENABLED`, which is off by default.
- Street and city can be filled in from a Dutch postcode and house number through the server
  (the respondent's browser and address are not shared with the address service, the house
  number addition is never sent, nothing that was asked is stored or logged, and the respondent
  can always type the address). It is behind a second setting, `ADDRESS_LOOKUP_ENABLED`, which is
  off by default, with rate limits per client and form (`API_ADDRESS_LOOKUP_*`). See
  `docs/address-question.md`.
- Webhooks, registrations and email actions can send an address answer: an object of its six
  parts (`street`, `house_number`, `house_number_addition`, `postcode`, `city`, `country`), as
  the public API answers it; an email action writes it as one line, and a condition on it
  compares the postcode.
