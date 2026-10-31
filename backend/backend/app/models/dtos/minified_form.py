import datetime as dt
from typing import Optional, List, Dict

from common.models.standard_form import (
    LOGO_ALT_MAX_LENGTH,
    LogoPosition,
    ParameterValue,
    Trigger,
    ActionState,
    WelcomePageField,
    EndingPages,
)
from common.models.standard_form import Theme
from fastapi_camelcase import CamelModel
from pydantic import Field

from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.models.dtos.response_dtos import (
    FormSettingsCamelModel,
    StandardFormFieldCamelModel,
)
from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.models.dtos.workspace_member_dto import FormImporterDetails


class FormDtoCamelModel(CamelModel):
    builder_version: Optional[str] = None
    form_id: Optional[str] = None
    imported_form_id: Optional[str] = None
    logo: Optional[str] = None
    logo_position: Optional[LogoPosition] = None
    logo_alt: Optional[str] = Field(None, max_length=LOGO_ALT_MAX_LENGTH)
    use_workspace_logo: Optional[bool] = None
    cover_image: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    button_text: Optional[str] = None
    settings: Optional[FormSettingsCamelModel] = None
    is_published: Optional[bool] = None
    is_multi_page: Optional[bool] = None
    created_at: Optional[dt.datetime] = None
    published_at: Optional[dt.datetime] = None
    consent: Optional[List[ConsentCamelModel]] = None
    responses: Optional[int] = None
    deletion_requests: Optional[int] = None
    groups: Optional[List[ResponderGroupDto]] = None
    imported_by: Optional[str] = None
    importer_details: Optional[FormImporterDetails] = None
    fields: Optional[List[StandardFormFieldCamelModel]] = None
    hidden_fields: Optional[List[str]] = None
    version: Optional[str | int] = None
    updated_at: Optional[dt.datetime] = None
    actions: Optional[Dict[Trigger, List[ActionState]]] = None
    parameters: Optional[Dict[str, List[ParameterValue]]] = None
    # Action credentials: readable in-process, never serialized into a response.
    secrets: Optional[Dict[str, List[ParameterValue]]] = Field(None, exclude=True)
    row_titles: Optional[List[str]] = None
    column_titles: Optional[List[str]] = None
    tabular_value: Optional[List[List[str]]] = None

    theme: Optional[Theme] = None
    welcome_page: Optional[WelcomePageField] = None
    thankyou_page: Optional[EndingPages] = None
    unauthorized: Optional[bool] = None
    # Why a respondent gets the welcome page alone, without the questions:
    # "closed" once the form's close date has passed (form_availability.py).
    unavailable: Optional[str] = None
    # Signed proof that this page shows the AI insights notice (#752): only on
    # the published form while the form allows AI insights. The form page
    # sends it back with the submission.
    ai_notice_token: Optional[str] = None
    # Only in the answer to a builder save: the field rules that save left
    # out because they were broken (``fieldId``, ``ruleId``, ``message``;
    # services/field_rules.py). Never stored.
    dropped_field_rules: Optional[List[Dict[str, Optional[str]]]] = None
    # Likewise the choice logic that save repaired (``fieldId``, ``optionId``,
    # ``message``; services/option_logic.py). Never stored.
    dropped_option_logic: Optional[List[Dict[str, Optional[str]]]] = None
    # Where a submission is also sent (registration): ``{"organisation": name}``,
    # only on the published form while the switch is on and its registration
    # is enabled. The privacy panel names it. Derived, never stored here.
    registration_destination: Optional[Dict[str, str]] = None
    # The hosts a submission is also sent to by the form's webhooks
    # (``{"hosts": [...]}``), only on the published form while WEBHOOKS_ENABLED
    # is on and a webhook is enabled. The privacy panel names them. Derived.
    webhook_destination: Optional[Dict[str, List[str]]] = None
    # The draft's version (its ETag, services/form_spec/editor_ops.py): only
    # on the editor's read, for If-Match on its op-batch saves.
    etag: Optional[str] = None
