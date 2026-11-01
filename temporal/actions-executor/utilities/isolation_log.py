"""What the executor says at start about its isolation (never fatal: a stack that
runs only the built-in actions has no use for the sandbox, and a run of custom
code fails closed when the child cannot confine itself)."""

import logging

from sandbox import broker
from settings.application import (
    isolation_enforced,
    refuse_key_when_not_allowed,
    settings,
)

logger = logging.getLogger(__name__)


async def log_isolation(key_needed: bool) -> None:
    """``key_needed``: this entry point still gets sealed secrets (the Temporal
    path), so the key is in use and no advice to remove it is given."""
    if not isolation_enforced():
        logger.error(
            "ACTION_ISOLATION=legacy: custom action code runs inside this process "
            "and can reach its keys, and outgoing calls follow no egress rules. "
            "Unset it unless you are rolling back."
        )
        return
    if not key_needed:
        # exits when ACTION_EXECUTOR_KEY_ALLOWED is off and the key is set
        refuse_key_when_not_allowed()
    broker.harden_parent()
    if settings.aes_hex_key and not key_needed:
        logger.warning(
            "AES_HEX_KEY is set on the executor: it is not used while the backend "
            "(4.3 or later) opens the run's secrets; remove it from this service "
            "and set ACTION_EXECUTOR_KEY_ALLOWED=false"
        )
    try:
        facts = await broker.probe()
        logger.info(
            "action sandbox ready: filesystem=%s seccomp=%s unprivileged=%s",
            facts.get("filesystem"),
            facts.get("seccomp"),
            facts.get("unprivileged"),
        )
    except broker.SandboxUnavailable as error:
        logger.error(
            "action sandbox NOT available, custom action code will not run: %s "
            "(docs/executor-isolation.md)",
            error,
        )
