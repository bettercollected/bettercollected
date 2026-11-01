# Address question and the street and city lookup

The address question collects a postal address: street, house number, an optional
addition, postcode, city and country. It has two switches, both off by default.

| Setting | Off (default) | On |
|---|---|---|
| `ADDRESS_QUESTION_ENABLED` | Builders cannot add or change an address question (422 `address_question_disabled`; the Insert menu leaves it out). Questions a form already has keep working. | The question is offered. Respondents type every part. |
| `ADDRESS_LOOKUP_ENABLED` | No outbound call is ever made; every address is typed. | For a Dutch address the form fills in street and city after the respondent has typed a postcode and a house number. Needs `ADDRESS_QUESTION_ENABLED`. |

Both are server settings like the other feature switches (docs/settings-inventory.md): a change reaches the
backend when it restarts.

## What is sent, and where

When the lookup is on, a respondent who has typed a Dutch postcode and a house number triggers one request
from **this server** to the **PDOK Locatieserver** address service (`api.pdok.nl`). The request carries the
postcode and the house number and nothing else: not the addition, not the form, the workspace, any other
answer, the respondent's browser or the respondent's IP address (the service sees this server only). The
service replies with the street and the city, which fill the two boxes; the respondent can change both.

- The host and the path of the service are fixed in the code (`services/address_lookup/provider.py`); there
  is no setting for them and nothing a form or a request contains can point the call elsewhere.
- The call goes through the same guarded client as the other outbound calls: https on port 443, the host is
  resolved at every call and must be a public address, the connection is pinned to the address checked, no
  redirects, a capped reply, a short timeout (5 s in all) and one attempt.
- Nothing is stored and nothing that was asked is logged: the logs hold our own failure codes only. A small
  in-memory cache (six hours for an address that was found, ten minutes for one that was not, at most 2,048
  entries, emptied when the process restarts) saves repeat calls.
- Mention the service in your privacy statement and processor list when you turn the lookup on. The
  respondent's privacy panel names it too.
- A street and a city that were looked up are **not verified**: the server checks their shape, not that the
  address exists.

## Limits

Per client and form 30 lookups a minute, per form 600 a minute (`API_ADDRESS_LOOKUP_PER_WINDOW`,
`API_ADDRESS_LOOKUP_FORM_PER_WINDOW`, `API_ADDRESS_LOOKUP_WINDOW_SECONDS`; 429 with `Retry-After` beyond).
At most 8 lookups run at once per process, and after five failures in a row the lookup pauses for 30 seconds.
When the service cannot answer, the respondent is told to type the address and nothing else changes.

## Before you turn the lookup on

Check it once by hand with an address you know: publish a form with an address question, open it, type the
postcode and the house number and see the street and the city fill in. The query and the reply follow the
service's documented search API and are covered in the tests with a fake transport only; no test or script
calls the real service.
