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
    ``submissions_api_enabled`` is the same for ``SUBMISSIONS_API_ENABLED``
    (the API key dialog offers the ``submissions:write`` scope from it).
    ``save_drafts_enabled`` is the same for ``SAVE_DRAFTS_ENABLED`` ("Let
    respondents save and continue later": the builder shows the setting
    read-only while it is off).
    ``form_revisions_ui_enabled`` is the same for ``FORM_REVISIONS_UI_ENABLED``
    (the Versions page of a form: list, compare, restore).
    ``audit_log_ui_enabled`` is the same for ``AUDIT_LOG_UI_ENABLED`` (the
    workspace's and a form's Activity pages: the audit log, for ``audit.read``).
    ``response_revisions_enabled`` is the same for ``RESPONSE_REVISIONS_ENABLED``
    (staff edit of answers and the history of a response).
    ``csv_import_enabled`` is the same for ``CSV_IMPORT_ENABLED`` (import
    responses from a CSV file: the responses screen offers it from it).
    ``form_embed_enabled`` is the same for ``FORM_EMBED_ENABLED`` (embedding
    forms in other sites: the share dialog's Embed tab and the Embedding
    settings page are shown only while it is on).
    ``form_access_enabled`` is the same for ``FORM_ACCESS_ENABLED`` (teams,
    grants on a form and restricted forms: the Teams tab and a form's Access
    settings are shown only while it is on).
    ``form_promotion_enabled`` is the same for ``FORM_PROMOTION_ENABLED`` (copying
    a form to another workspace: the form menu's "Copy to another workspace" and
    the form file are shown only while it is on).
    ``api_key_roles_enabled`` is the same for ``API_KEY_ROLES_ENABLED`` (a role
    and a list of forms on an API key: the key dialog's role and forms controls
    are shown only while it is on).
    ``reporting_enabled`` is the same for ``REPORTING_ENABLED`` (reports on a
    form's answers: the Report page is shown only while it is on)."""

    permissions: List[Permission] = []
    field_rules_enabled: bool = False
    # Likewise for choice logic (``CHOICE_LOGIC_ENABLED``): the builder shows
    # its option logic and filter settings from it.
    choice_logic_enabled: bool = False
    save_drafts_enabled: bool = False
    csv_import_enabled: bool = False
    new_question_types_enabled: bool = False
    address_question_enabled: bool = False
    address_lookup_enabled: bool = False
    signature_question_enabled: bool = False
    option_sources_enabled: bool = False
    reusable_sections_enabled: bool = False
    layout_containers_enabled: bool = False
    form_revisions_ui_enabled: bool = False
    audit_log_ui_enabled: bool = False
    response_revisions_enabled: bool = False
    submissions_api_enabled: bool = False
    form_embed_enabled: bool = False
    form_access_enabled: bool = False
    form_promotion_enabled: bool = False
    api_key_roles_enabled: bool = False
    reporting_enabled: bool = False
