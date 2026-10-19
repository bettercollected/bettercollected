"""Wires the loops to a portal's services."""

from __future__ import annotations

from backend.admin.loops.base import LoopRunner
from backend.admin.loops.integrity import IntegrityMonitor
from backend.admin.loops.notifications import NotificationSender
from backend.admin.loops.retention import RetentionLoop


def build_runner(portal) -> LoopRunner:
    from backend.admin.services.settings_store import SettingsService, store_registry
    from common.settings.keys import SectionKeys

    registry = store_registry()
    keys = SectionKeys(
        portal.master_key,
        sections={s.section for s in registry},
        master_previous=portal.master_previous,
    )
    service = SettingsService(portal.engine, registry, keys)
    cfg = portal.loop_settings

    async def audit_step():
        from backend.admin.services import audit

        async with portal.engine.begin() as conn:
            return await audit.verify_step(conn)

    def known_keys() -> frozenset:
        return frozenset(spec.key for spec in registry)

    loops = [
        NotificationSender(
            portal.engine,
            portal.clock,
            portal.mailer,
            lambda: sorted(portal.settings.admin_emails),
            portal.board,
            interval=cfg.notify_interval,
            max_per_minute=cfg.notify_max_per_minute,
        ),
        RetentionLoop(
            portal.engine,
            portal.clock,
            portal.sessions.cleanup,
            portal.limiter.cleanup,
            interval=cfg.retention_interval,
        ),
        IntegrityMonitor(
            portal.engine,
            portal.clock,
            service.verify,
            portal.board,
            interval=cfg.integrity_interval,
            audit_step=audit_step,
            known_keys=known_keys,
        ),
    ]
    return LoopRunner(portal.engine, portal.clock, loops, portal.board)
