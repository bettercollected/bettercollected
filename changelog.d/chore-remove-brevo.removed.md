- The Brevo marketing tracker is gone: sign-ups, upgrades and other platform events no longer send
  an email address to a marketing tool, and account deletion no longer calls Brevo to erase a
  contact (the one-off `python -m auth.brevo_contacts` command is removed too). The optional event
  webhook (`EVENT_WEBHOOK_URL`) stays and carries the event type and user id only.
  `BREVO_TRACKER_KEY`, `BREVO_TRACKER_API_URL` and `BREVO_CONTACTS_API_KEY` can be dropped from
  deployments; leaving them set is harmless (they are ignored, as are stored rows for them).
