- The workspace audit log can be read: `GET /workspaces/{id}/audit-log` and
  `GET /workspaces/{id}/forms/{form_id}/audit-log`, behind `AUDIT_LOG_UI_ENABLED` (off by default,
  422 `audit_log_off` while off; events are recorded either way). Owners, Admins and Privacy
  officers (`audit.read`) read entries newest first in pages of 20 (at most 100), filtered by kind,
  person, form and date range. An entry holds codes and ids only: a Privacy officer sees who did
  what to which form and when, with no response link and no session id, and a member who has left
  shows without a name. Adds migration 0038 (indexes behind the filters) and
  `auditLogUiEnabled` in the workspace permissions. See `docs/audit-log.md`.
