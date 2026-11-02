"""API key roles and form scope (docs/enterprise-access-model.md, section 4),
behind ``API_KEY_ROLES_ENABLED``.

A key acts as its creator, narrowed: its permissions on a form are the
creator's current ones, intersected with the key's role ceiling and (for a key
limited to a list of forms) the ceiling of the key's row for that form. It
never adds to its creator. ``model`` holds the pure decision; ``mode`` the
switch; ``services/api_access.py`` is the only place a key's decision is taken.
"""
