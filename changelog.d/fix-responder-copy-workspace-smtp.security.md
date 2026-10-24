- Actions: the respondent's copy of a response keeps the workspace's title as the sender's name and
  the form's title in the subject only when it goes through the workspace's own SMTP server, from
  the address the workspace configured (both set on the workspace or the form). Through the
  action's defaults, which the instance's administrators set, it no longer carries a workspace's
  name. Every From name and subject an action mail gets, custom actions' included, is folded to one
  line (line breaks and control characters become spaces, invisible formatting characters are
  dropped) and capped at 78 and 120 characters, so a title can no longer add mail headers.
