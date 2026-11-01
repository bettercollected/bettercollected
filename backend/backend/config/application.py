"""Application configuration - FastAPI."""

import os
from pathlib import Path
from typing import Optional

from common.configs.shipped_secrets import require_secrets
from common.services.keyset_source import configured_key_ids
from common.settings.loader import (
    ensure_poller,
    expose_live,
    load_snapshot,
    set_keyset_key_ids,
)
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings

from backend.config.api_settings import ApiSettings
from backend.config.apm_settings import APMSettings
from backend.config.auth_settings import AuthSettings
from backend.config.aws import AWSSettings
from backend.config.coupon_code_settings import CouponCodeSettings
from backend.config.custom_domain import CustomDomainSettings
from backend.config.database import MongoSettings
from backend.config.events_webhook import EventsWebhook
from backend.config.https_certificate import HttpsCertificateApiSettings
from backend.config.ai_settings import AISettings
from backend.config.google_ai_settings import GoogleAISettings
from backend.config.google_forms_settings import GoogleFormsSettings
from backend.config.google_sheets_settings import GoogleSheetsSettings
from backend.config.OpenAISettings import OpenAISettings
from backend.config.open_formulieren_settings import OpenFormulierenSettings
from backend.config.registration_settings import RegistrationSettings
from backend.config.webhooks_settings import WebhooksSettings
from backend.config.email_actions_settings import EmailActionsSettings
from backend.config.mail_settings import MailSettings
from backend.config.respondent_identity_settings import RespondentIdentitySettings
from backend.config.pdf_import_settings import PdfImportSettings
from backend.config.unsplash_settings import UnsplashSettings
from backend.config.scim_settings import SCIMSettings
from backend.config.sso_settings import SSOSettings
from backend.config.template_settings import DefaultResourcesWorkspaceSettings
from backend.config.temporal_settings import TemporalSettings
from backend.config.UmamiSettings import UmamiSettings
from backend.config.verified_domain_settings import VerifiedDomainSettings

default_dot_env_path = (
    Path(os.path.abspath(os.path.dirname(__file__)))
    .parent.parent.absolute()
    .joinpath(".env")
)
load_dotenv(os.getenv("DOTENV_PATH", default_dot_env_path))

# Settings may come from the signed settings store (SETTINGS_STORE=off|auto|
# required; auto and unconfigured means environment and defaults only). One
# snapshot is read here, before the settings classes below are built.
load_snapshot(
    "backend",
    required_env_keys=("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY"),
)



class Application(StoreBackedSettings):
    """Define application configuration model.

    Constructor will attempt to determine the values of any fields not passed
    as keyword arguments by reading from the environment. Default values will
    still be used if the matching environment variable is not set.

    Attributes:
        DEBUG (bool): FastAPI debug mode (HTML tracebacks for unhandled
            errors). Off unless explicitly enabled; keep it off in production.
    """

    DEBUG: bool = False
    ENABLE_SUGGEST_PRICE: bool = False
    # Submitted answers are checked against the form (Required, answer rules,
    # types; services/answer_validation.py). False = "log only": problems are
    # logged (form id, count, rule codes) and the response is stored anyway.
    RESPONSE_VALIDATION_ENFORCE: bool = True
    # Field rules (services/field_rules.py) may be created or changed through
    # the API, the builder save, editor ops and templates. Off (the default,
    # until an operator turns rules on): those saves are refused with 422
    # field_rules_disabled; stored rules are kept and still enforced.
    FIELD_RULES_ENABLED: bool = False
    # The newer question types (time, day, currency, date range, tags) may be added or changed through the API, the builder save,
    # edit operations (MCP and AI included), templates and imports
    # (services/new_question_types.py). Off (the default, until the release
    # that turns them on): those saves are refused with 422
    # question_type_disabled; questions already stored keep working.
    NEW_QUESTION_TYPES_ENABLED: bool = False
    # The address question (street, house number, postcode, city, country;
    # common/address.py) may be added or changed through the same paths. Off
    # (the default, until the release that turns it on): those saves are
    # refused with 422 address_question_disabled; an address question already
    # stored keeps being shown, answered and exported.
    ADDRESS_QUESTION_ENABLED: bool = False
    # The street and city lookup of the address question
    # (services/address_lookup/): a Dutch postcode and house number are sent,
    # through this server, to a third-party address service. Off (the default):
    # no outbound call, every address is typed. Needs ADDRESS_QUESTION_ENABLED.
    ADDRESS_LOOKUP_ENABLED: bool = False
    # The signature question (a drawn or typed signature, services/signatures.py)
    # may be added or changed through the same paths. Off (the default, until
    # the release that turns it on): those saves are refused with 422
    # signature_question_disabled; a signature question already stored keeps
    # being shown, answered and exported.
    SIGNATURE_QUESTION_ENABLED: bool = False
    # Layout containers (panels, tabs and field sets that group the questions
    # of a page, services/layout_containers.py) may be added or changed through
    # the same paths. Off (the default, until the release that turns it on):
    # those saves are refused with 422 layout_containers_disabled; containers a
    # form already has keep being shown and may lose questions or be removed.
    LAYOUT_CONTAINERS_ENABLED: bool = False
    # The public API's submissions endpoints (services/submissions_api): a
    # workspace API key with the submissions:write scope creates and updates
    # responses through the respondent's own submit path. Off (the default,
    # until the release that turns it on): both endpoints answer 404, the
    # scope can't be granted and a key that has it is refused; responses that
    # were made this way stay as they are.
    SUBMISSIONS_API_ENABLED: bool = False
    # Choice logic (services/option_logic.py: options shown or hidden by
    # answers, options filtered by an earlier answer) may be created or
    # changed through the API, the builder save, edit operations, templates and
    # the AI and MCP paths. Off (the default, kept off until the 4.2
    # release): those saves are refused with 422 choice_logic_disabled;
    # stored choice logic is kept and still enforced.
    CHOICE_LOGIC_ENABLED: bool = False
    # Respondents may save a draft and continue later (services/form_drafts).
    # Off (the default, until it is released): turning the per-form setting on
    # is refused with 422 save_drafts_disabled, and saving or opening a draft is
    # refused.
    SAVE_DRAFTS_ENABLED: bool = False
    # The admin task runner presents this key to the internal admin-task
    # routes (controllers/admin_tasks_router.py; the runner's
    # ADMIN_TASKS_API_KEY). Empty: those routes answer 503.
    ADMIN_TASKS_API_KEY: str = ""
    apm_settings: APMSettings = APMSettings()
    api_settings: ApiSettings = ApiSettings()
    auth_settings: AuthSettings = AuthSettings()
    respondent_identity: RespondentIdentitySettings = RespondentIdentitySettings()
    mongo_settings: MongoSettings = MongoSettings()
    aws_settings: AWSSettings = AWSSettings()
    https_cert_api_settings: HttpsCertificateApiSettings = HttpsCertificateApiSettings()
    custom_domain: CustomDomainSettings = CustomDomainSettings()
    temporal_settings: TemporalSettings = TemporalSettings()
    default_workspace_settings: DefaultResourcesWorkspaceSettings = (
        DefaultResourcesWorkspaceSettings()
    )
    event_webhook_settings: EventsWebhook = EventsWebhook()
    coupon_settings: CouponCodeSettings = CouponCodeSettings()
    ai: AISettings = AISettings()
    open_ai: OpenAISettings = OpenAISettings()
    google_ai: GoogleAISettings = GoogleAISettings()
    google_forms: GoogleFormsSettings = GoogleFormsSettings()
    open_formulieren: OpenFormulierenSettings = OpenFormulierenSettings()
    google_sheets: GoogleSheetsSettings = GoogleSheetsSettings()
    unsplash: UnsplashSettings = UnsplashSettings()
    umami_settings: UmamiSettings = UmamiSettings()
    pdf_import: PdfImportSettings = PdfImportSettings()
    verified_domains: VerifiedDomainSettings = VerifiedDomainSettings()
    sso: SSOSettings = SSOSettings()
    scim: SCIMSettings = SCIMSettings()
    registration: RegistrationSettings = RegistrationSettings()
    webhooks: WebhooksSettings = WebhooksSettings()
    email_actions: EmailActionsSettings = EmailActionsSettings()
    mail_settings: MailSettings = MailSettings()
    # the From display name of mails the backend sends (never a workspace's)
    ORGANIZATION_NAME: Optional[str] = "Better Collected"
    # All your additional application configuration should go either here or in
    # separate file in this submodule.

    model_config = SettingsConfigDict(case_sensitive=False)


settings = Application()

# Hot (class H) settings are read through live(), for example live().ai.X
expose_live("ai", settings.ai)
expose_live("api", settings.api_settings)


# Key ids (never key material) of MASTER_ENCRYPTION_KEYSET, for the fingerprint
# this service reports to the settings store: the environment, else the store's
# verified row (common.services.keyset_source).
keyset_key_ids = configured_key_ids


set_keyset_key_ids(keyset_key_ids)
ensure_poller()  # no-op when the store is off

# Session tokens are signed with AUTH_JWT_SECRET and OAuth/SSO state, action
# and SCIM secrets are encrypted with AUTH_AES_HEX_KEY: never run with either
# unset or set to a value published in the repository.
require_secrets(
    "the backend",
    jwt_secrets={"AUTH_JWT_SECRET": settings.auth_settings.JWT_SECRET},
    fernet_keys={"AUTH_AES_HEX_KEY": settings.auth_settings.AES_HEX_KEY},
)
