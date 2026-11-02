- The workspace audit log now records changes to workspace security settings and to a form's
  integrations. Settings: single sign-on connections (created, enabled, disabled, deleted), the
  require-single-sign-on switch and the default role it gives, verified email domains (claimed,
  verified, removed), directory sync (the token created, replaced or revoked, and a group mapped to
  a role), the AI consent and the custom domain. Integrations: an email action (created, changed,
  switched on or off, deleted) and a case-system service or a form's registration to one (created,
  changed, switched on or off, deleted). Entries hold ids, enum values and the names of the parts
  that changed, never an address, a URL, a hostname, a template, a name, a token or a secret.
  Changes that open access, send answers somewhere new or remove configuration are written before
  the change and refused (503 `audit_unavailable`, nothing changed) when the entry cannot be
  stored; closing a way in and the inert ones are best effort. Nothing reads these entries in the
  product yet.
