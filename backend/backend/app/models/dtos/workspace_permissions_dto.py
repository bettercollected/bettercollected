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
    (``NEW_QUESTION_TYPES_ENABLED``): the builder offers them from it.
    ``address_question_enabled`` is the same for the address question
    (``ADDRESS_QUESTION_ENABLED``); ``address_lookup_enabled`` says whether the
    street and city lookup works too (both it and ``ADDRESS_LOOKUP_ENABLED``
    are on): the builder says so next to the question's lookup setting.
    ``signature_question_enabled`` is the same for the signature question
    (``SIGNATURE_QUESTION_ENABLED``).
    ``option_sources_enabled`` is the same for options taken from a workspace
    list or another form's answers (``OPTION_SOURCES_ENABLED``): the builder
    offers the source picker and the workspace its lists page from it.
    ``reusable_sections_enabled`` is the same for the workspace library of
    reusable sections (``REUSABLE_SECTIONS_ENABLED``): the builder offers "Save
    as section", the Insert menu's Sections group and "Update from library",
    and the workspace its library page, from it.
    ``layout_containers_enabled`` is the same for panels, tabs and field sets
    (``LAYOUT_CONTAINERS_ENABLED``).
    ``save_drafts_enabled`` is the same for ``SAVE_DRAFTS_ENABLED`` ("Let
    respondents save and continue later": the builder shows the setting
    read-only while it is off)."""

    permissions: List[Permission] = []
    field_rules_enabled: bool = False
    # Likewise for choice logic (``CHOICE_LOGIC_ENABLED``): the builder shows
    # its option logic and filter settings from it.
    choice_logic_enabled: bool = False
    save_drafts_enabled: bool = False
    new_question_types_enabled: bool = False
    address_question_enabled: bool = False
    address_lookup_enabled: bool = False
    signature_question_enabled: bool = False
    option_sources_enabled: bool = False
    reusable_sections_enabled: bool = False
    layout_containers_enabled: bool = False
