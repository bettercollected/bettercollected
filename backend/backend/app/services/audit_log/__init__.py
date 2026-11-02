"""The workspace audit log, read (docs/audit-log.md): the two read-only routes
behind ``AUDIT_LOG_UI_ENABLED`` that list ``workspace_audit_events`` for staff
holding ``audit.read``.

``catalog`` is the one list of event kinds the API knows and the area each
belongs to; ``mode`` the switch; ``retention`` how long a workspace's entries
are kept (what the page states); ``reader`` the filters, the keyset page, the
permissions and the names the ids resolve to. Nothing here writes: the writers
are the ones that always were (``form_access/audit.py``,
``response_revisions/audit.py``, ``sso/policy.py``, ``mfa``,
``api_key_lifecycle.py``) and are never switched.
"""
