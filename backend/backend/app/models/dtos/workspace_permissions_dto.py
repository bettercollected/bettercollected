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
    ``layout_containers_enabled`` is the same for panels, tabs and field sets
    (``LAYOUT_CONTAINERS_ENABLED``).
    ``submissions_api_enabled`` is the same for ``SUBMISSIONS_API_ENABLED``
    (the API key dialog offers the ``submissions:write`` scope from it).
    ``save_drafts_enabled`` is the same for ``SAVE_DRAFTS_ENABLED`` ("Let
    respondents save and continue later": the builder shows the setting
    read-only while it is off).
    ``form_revisions_ui_enabled`` is the same for ``FORM_REVISIONS_UI_ENABLED``
    (the Versions page of a form: list, compare, restore).
    ``form_embed_enabled`` is the same for ``FORM_EMBED_ENABLED`` (embedding
    forms in other sites: the share dialog's Embed tab and the Embedding
    settings page are shown only while it is on)."""

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
    layout_containers_enabled: bool = False
    form_revisions_ui_enabled: bool = False
    submissions_api_enabled: bool = False
    form_embed_enabled: bool = False
