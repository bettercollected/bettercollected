from typing import List

from fastapi_camelcase import CamelModel

from backend.app.models.enum.permission import Permission


class WorkspacePermissionsDto(CamelModel):
    """The caller's effective permissions in a workspace; empty when they
    hold none there (not a member, a disabled membership or workspace).

    ``field_rules_enabled`` says whether this server accepts new or changed
    field rules (``FIELD_RULES_ENABLED``): the builder shows its rules editor
    from it, so the one switch on the backend is the only one.
    ``choice_logic_enabled`` is the same for option logic and filters, and
    ``save_drafts_enabled`` for ``SAVE_DRAFTS_ENABLED`` ("Let respondents save
    and continue later": the builder shows the setting read-only while it is
    off)."""

    permissions: List[Permission] = []
    field_rules_enabled: bool = False
    # Likewise for choice logic (``CHOICE_LOGIC_ENABLED``): the builder shows
    # its option logic and filter settings from it.
    choice_logic_enabled: bool = False
    save_drafts_enabled: bool = False
