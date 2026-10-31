- Email actions per form (off by default, `EMAIL_ACTIONS_ENABLED`). Owners and admins mail the form's team when a
  response is submitted, from English and Dutch templates (plain text, placeholders for the questions they choose)
  with a preview and a test mail to themselves. Team addresses must be members of the workspace, checked when saved
  and again when sent. A copy for the respondent uses fixed wording, goes only to the address typed in that
  submission and is rate limited. Mails are sent by the jobs worker on a new `emails` queue with retries, and the
  action log (ids, status and timings, no addresses or content, 30 days) shows them. The respondent's privacy panel
  says who is mailed.
  Upgrade note: the jobs worker now serves `default`, `webhooks` and `emails`; if you set `JOBS_QUEUES`, include
  `emails`. The backend now reads the `MAIL_*` settings of the mail server the auth service uses.
- Webhooks and email actions can run only when a condition on the answers holds, built in the form's own logic
  conditions and checked by the server when the submission arrives. A submission that does not match is logged as
  cancelled, with no answers.
