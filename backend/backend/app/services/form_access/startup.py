"""The startup notice for ``FORM_ACCESS_ENABLED`` being off while form-level
access data is stored.

Off, nothing form-level is enforced: a restricted form is open to every member
by their workspace role. That is the defined rollback behaviour, but an
operator who switches the setting off (or never switched it on after a
release that stored restricted forms) should be told once, at boot. The log
line carries counts only: no workspace, form or team ids, no titles or names.

Never blocks or slows the start: the switch on costs no query; the switch off
costs one bounded read (statement timeout and an overall time limit), and any
failure is logged at debug level by class only.
"""

from __future__ import annotations

import asyncio
from typing import NamedTuple, Optional

from loguru import logger
from sqlalchemy import text

from backend.app.services.form_access.mode import form_access_enabled

# ``is_restricted`` (services/form_access/model.py) in SQL: a stored mode other
# than "workspace" restricts; with no mode stored, a Private (hidden) form does.
_COUNTS = text(
    """
    SELECT
      (SELECT count(*) FROM app.workspace_forms
        WHERE CASE
                WHEN doc #>> '{settings,access_mode}' IS NULL THEN hidden IS TRUE
                ELSE doc #>> '{settings,access_mode}' <> 'workspace'
              END) AS restricted_forms,
      (SELECT count(*) FROM app.form_access_grants) AS grants,
      (SELECT count(*) FROM app.member_groups) AS teams
    """
)

# the read is given this long inside the database, and this long overall
# (connection wait included); both are far above what a count of a few
# thousand rows needs
STATEMENT_TIMEOUT_MS = 2000
OVERALL_TIMEOUT_S = 5.0


class FormAccessCounts(NamedTuple):
    restricted_forms: int
    grants: int
    teams: int

    @property
    def any(self) -> bool:
        return bool(self.restricted_forms or self.grants or self.teams)


async def _read_counts(sessionmaker) -> FormAccessCounts:
    async with sessionmaker() as session:
        async with session.begin():
            await session.execute(
                text(f"SET LOCAL statement_timeout = {int(STATEMENT_TIMEOUT_MS)}")
            )
            row = (await session.execute(_COUNTS)).one()
    return FormAccessCounts(int(row[0]), int(row[1]), int(row[2]))


def warning_message(counts: FormAccessCounts) -> str:
    return (
        "FORM_ACCESS_ENABLED is off while form-level access data is stored "
        f"({counts.restricted_forms} restricted forms, {counts.grants} grants, "
        f"{counts.teams} teams): those forms are open to every member's workspace "
        "role until it is switched on."
    )


async def log_if_form_access_data_stored(
    sessionmaker, *, overall_timeout_s: float = OVERALL_TIMEOUT_S
) -> Optional[FormAccessCounts]:
    """Log one warning when the switch is off and restricted forms, grants or
    teams are stored; returns the counts when it warned, else None. Switch on:
    no query. Never raises."""
    if form_access_enabled() or sessionmaker is None:
        return None
    try:
        counts = await asyncio.wait_for(
            _read_counts(sessionmaker), timeout=overall_timeout_s
        )
    except Exception as exc:  # noqa: BLE001 - never blocks the start; class only
        logger.debug(
            "form access: the startup count was skipped ({})", type(exc).__name__
        )
        return None
    if not counts.any:
        return None
    logger.warning(warning_message(counts))
    return counts
