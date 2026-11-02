- The dashboard has an Activity page (`/dashboard/activity`) and, for each form, an Activity item
  after Versions: who changed what, newest first, one plain sentence per entry in English or
  Dutch, filtered by type, person, form and date range (kept in the address, so a view can be
  sent to a colleague), with "Show older entries" paging and the retention period stated. Owners,
  Admins and Privacy officers (`audit.read`) see it, only while `AUDIT_LOG_UI_ENABLED` is on; a
  Privacy officer sees no response links and no session ids. See `docs/audit-log.md`.
