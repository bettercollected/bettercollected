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
Before any of that, one client may send at most four times the per-client limit to one backend process per window
(in memory, no database query; 429 beyond), and a form that cannot be looked up is remembered for 30 seconds, so
guessing form addresses costs the database next to nothing.
At most 8 lookups run at once per process, and one process makes at most 10 calls a second and 300 a minute to
the service; past either, the answer is "unavailable" at once and the respondent types the address (answers from the
cache are not calls and are still given). After five failures in a row the lookup pauses for 30 seconds.
When the service cannot answer, the respondent is told to type the address and nothing else changes.

The in-memory tables (answers, forms that cannot be looked up, forms that can, the per-client counters) are bounded
and drop the entry used longest ago first, so a flood of new clients or forms cannot reset what the active ones have
used.

## Which forms answer

The route is public like the form, and it answers for the same forms a respondent without an account may fill in
right now, read the way the submit gate reads them: a form that is closed (from its close date on), not open yet
(before its open date) or full (it holds as many responses as its limit) does not answer, and neither does a
private form (restricted to responder groups) or a hidden one. All of them give the same 404 as an unknown form,
and nothing is sent to the service. The dates are judged at every call; a form's state is read once per 30 seconds
(a form whose limit was just reached answers for up to 30 seconds more). Respondents of a restricted form type
their address.

## Before you turn the lookup on

Behind a reverse proxy or a load balancer, set `TRUSTED_PROXIES` to the proxy's address (or the network between
the proxy and the backend) first. The limits above are counted per client address, and without it the backend sees
only the proxy: every respondent then shares one bucket, so a busy form is refused after 30 lookups a minute for
everybody. The same happens for requests whose client address cannot be read at all: they count together as
"unknown". The backend logs a warning once when it sees forwarding headers from a private address while
`TRUSTED_PROXIES` is empty.

Check it once by hand with an address you know: publish a form with an address question, open it, type the
postcode and the house number and see the street and the city fill in. The query and the reply follow the
service's documented search API and are covered in the tests with a fake transport only; no test or script
calls the real service.
