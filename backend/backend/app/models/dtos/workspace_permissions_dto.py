from typing import List

from fastapi_camelcase import CamelModel

from backend.app.models.enum.permission import Permission


class WorkspacePermissionsDto(CamelModel):
    """The caller's effective permissions in a workspace; empty when they
    hold none there (not a member, a disabled membership or workspace).

    ``field_rules_enabled`` says whether this server accepts new or changed
    field rules (``FIELD_RULES_ENABLED``): the builder shows its rules editor
    from it, so the one switch on the backend is the only one.
    ``choice_logic_enabled`` is the same for option logic and filters.
    ``new_question_types_enabled`` is the same for the newer question types
    (``NEW_QUESTION_TYPES_ENABLED``): the builder offers them from it."""

    permissions: List[Permission] = []
    field_rules_enabled: bool = False
    # Likewise for choice logic (``CHOICE_LOGIC_ENABLED``): the builder shows
    # its option logic and filter settings from it.
    choice_logic_enabled: bool = False
    new_question_types_enabled: bool = False
