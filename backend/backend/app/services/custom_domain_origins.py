"""Custom domains as allowed browser origins.

A workspace's custom domain is an allowed origin (``https://<hostname>``) only
while the domain is verified: ``custom_domain_verified`` on the workspace, set
from the custom-domain service's ``ready`` status or the legacy verification.
Every place that changes a workspace's domain or its verification goes through
``sync_custom_domain_origin`` / ``remove_custom_domain_origin``, and
``prune_unverified_origins`` brings stored data in line with the same rule.
"""

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlsplit

from backend.app.middlewares.dynamic_cors_middleware import DynamicCORSMiddleware
from backend.config import settings

HTTPS = "https://"
# allowed_origins has no unique index; never loop forever on a broken store
_MAX_DUPLICATES = 50


def custom_domain_origin(hostname: str) -> str:
    return HTTPS + hostname


async def _remove_origin(origins_repo, origin: str) -> bool:
    removed = False
    for _ in range(_MAX_DUPLICATES):
        if not await origins_repo.find_by_origin(origin):
            break
        await origins_repo.delete_by_origin(origin)
        removed = True
    return removed


async def remove_custom_domain_origin(
    origins_repo, hostname: Optional[str], refresh: bool = True
) -> bool:
    """Stop accepting ``hostname`` as an origin. Returns whether anything changed."""
    if not hostname:
        return False
    removed = await _remove_origin(origins_repo, custom_domain_origin(hostname))
    if removed and refresh:
        await DynamicCORSMiddleware.force_refresh_origins()
    return removed


async def sync_custom_domain_origin(
    origins_repo, hostname: Optional[str], verified: bool
) -> bool:
    """Accept ``hostname`` as an origin if and only if it is verified.
    Returns whether anything changed."""
    if not hostname:
        return False
    origin = custom_domain_origin(hostname)
    if not verified:
        return await remove_custom_domain_origin(origins_repo, hostname)
    if await origins_repo.find_by_origin(origin):
        return False
    await origins_repo.add(origin)
    await DynamicCORSMiddleware.force_refresh_origins()
    return True


def _origin_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def static_origins(extra: Iterable[str] = ()) -> set:
    """Origins never treated as custom domains: the client app's own origin
    and whatever the operator passes."""
    origins = {_origin_of(settings.api_settings.CLIENT_URL)}
    origins.update(_origin_of(origin) for origin in extra)
    origins.discard(None)
    return origins


async def prune_unverified_origins(
    origins_repo,
    workspace_repo,
    *,
    include_orphans: bool = False,
    keep: Iterable[str] = (),
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Remove allowed origins of custom domains that are not verified.

    An ``https://`` origin whose hostname is a workspace's custom domain is
    kept only while that workspace's domain is verified. Origins that match no
    workspace ("orphans") cannot be told apart from first-party origins seeded
    by hand, so they are only reported unless ``include_orphans`` is set; the
    client app's origin and ``keep`` are never removed. Idempotent."""
    protected = static_origins(keep)
    removed: List[str] = []
    orphans: List[str] = []
    for origin in sorted(set(await origins_repo.list_origins())):
        if origin in protected or not origin.startswith(HTTPS):
            continue
        hostname = origin[len(HTTPS) :]
        workspace = await workspace_repo.find_by_custom_domain(hostname)
        if workspace is None:
            orphans.append(origin)
            if not include_orphans:
                continue
        elif workspace.custom_domain_verified:
            continue
        removed.append(origin)
        if not dry_run:
            await _remove_origin(origins_repo, origin)
    if removed and not dry_run:
        await DynamicCORSMiddleware.force_refresh_origins()
    return {"removed": removed, "orphans": orphans, "dry_run": dry_run}
