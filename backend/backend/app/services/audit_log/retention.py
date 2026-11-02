"""How long a workspace's audit entries are kept, as the page states it.

Today one figure holds for the whole table (``AUDIT_RETENTION``, a year, what
the daily purge deletes by). The reader asks here, per workspace, and never
holds a number of its own: when the retention becomes a choice of the workspace
this is the one function that changes.
"""

from backend.app.services.sso.policy import AUDIT_RETENTION


async def retention_days(workspace_id) -> int:
    """The number of days the entries of ``workspace_id`` are kept."""
    return int(AUDIT_RETENTION.days)
