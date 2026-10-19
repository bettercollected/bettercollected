"""Where a service's ``MASTER_ENCRYPTION_KEYSET`` comes from, without loading it.

The environment (an operator's override, also what a stack that predates the
settings store has) wins; otherwise the settings store's verified row. Kept
apart from ``crypto_service``, which builds the process-wide cipher when it is
imported: a service's configuration registers ``configured_key_ids`` before the
settings snapshot is loaded, so importing this module must have no side effects.
"""

import os

from common.services.keyset import KEYSET_ENV, parse_keyset

__all__ = ["configured_keyset", "configured_key_ids"]


def configured_keyset() -> str:
    """The keyset value this process resolves ("" when there is none)."""
    value = (os.environ.get(KEYSET_ENV) or "").strip()
    if value:
        return value
    from common.settings.loader import current_runtime

    runtime = current_runtime()
    resolved = runtime.resolve_key(KEYSET_ENV) if runtime is not None else None
    return (resolved.value or "").strip() if resolved is not None else ""


def configured_key_ids():
    """Key ids (never key material) of the resolved keyset, for the fingerprint a
    service reports in its settings-store heartbeat
    (``common.settings.loader.set_keyset_key_ids``). Every service that loads the
    keyset registers it: without it the heartbeat carries no keyset fingerprint
    and the admin keyset tasks refuse to promote, re-encrypt or drop a key."""
    return [key.key_id for key in parse_keyset(configured_keyset()).key]
