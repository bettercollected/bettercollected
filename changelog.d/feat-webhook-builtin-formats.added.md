- Webhooks have a `format`, shown in the webhooks list. Besides the signed `envelope` there are
  `legacy_list` (the bare list of questions and answers the built-in "send a webhook" action posted,
  now also signed), `slack` and `discord` (the messages the built-in Slack and Discord actions
  posted). They exist for built-in actions that move into webhooks in 4.4 and send every question:
  a creator cannot choose them, and can only move a `legacy_list` webhook to the `envelope` format.
  A Slack or Discord webhook only goes to that service's own webhook address.
