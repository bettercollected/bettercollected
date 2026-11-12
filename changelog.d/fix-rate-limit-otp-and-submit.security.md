- Hardening: sign-in code mails (respondent and creator) are now rate limited per
  address (3 an hour), per client (10 an hour), per workspace (1000 an hour) and for
  the instance (5000 an hour), and a response submit per client and form (120 a
  minute) and per form (1000 a minute). A refusal is a plain 429 in English or Dutch
  with `Retry-After`, the same whether or not the address has an account. The sign-in
  and form screens show it in the respondent's language. A client whose address cannot
  be told is limited by address, workspace, instance and form only. The Submissions API
  keeps its own limits.
