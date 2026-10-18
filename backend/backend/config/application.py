"""Application configuration - FastAPI."""

import os
from pathlib import Path

from common.configs.shipped_secrets import require_secrets
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.config.api_settings import ApiSettings
from backend.config.apm_settings import APMSettings
from backend.config.auth_settings import AuthSettings
from backend.config.aws import AWSSettings
from backend.config.brevo_settings import BrevoSettings
from backend.config.coupon_code_settings import CouponCodeSettings
from backend.config.custom_domain import CustomDomainSettings
from backend.config.database import MongoSettings
from backend.config.events_webhook import EventsWebhook
from backend.config.https_certificate import HttpsCertificateApiSettings
from backend.config.ai_settings import AISettings
from backend.config.google_ai_settings import GoogleAISettings
from backend.config.OpenAISettings import OpenAISettings
from backend.config.pdf_import_settings import PdfImportSettings
from backend.config.unsplash_settings import UnsplashSettings
from backend.config.scim_settings import SCIMSettings
from backend.config.sentry_setting import SentrySettings
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


class Application(BaseSettings):
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
    apm_settings: APMSettings = APMSettings()
    api_settings: ApiSettings = ApiSettings()
    auth_settings: AuthSettings = AuthSettings()
    mongo_settings: MongoSettings = MongoSettings()
    aws_settings: AWSSettings = AWSSettings()
    https_cert_api_settings: HttpsCertificateApiSettings = HttpsCertificateApiSettings()
    custom_domain: CustomDomainSettings = CustomDomainSettings()
    sentry_settings: SentrySettings = SentrySettings()
    temporal_settings: TemporalSettings = TemporalSettings()
    default_workspace_settings: DefaultResourcesWorkspaceSettings = (
        DefaultResourcesWorkspaceSettings()
    )
    event_webhook_settings: EventsWebhook = EventsWebhook()
    coupon_settings: CouponCodeSettings = CouponCodeSettings()
    ai: AISettings = AISettings()
    open_ai: OpenAISettings = OpenAISettings()
    google_ai: GoogleAISettings = GoogleAISettings()
    unsplash: UnsplashSettings = UnsplashSettings()
    brevo_settings: BrevoSettings = BrevoSettings()
    umami_settings: UmamiSettings = UmamiSettings()
    pdf_import: PdfImportSettings = PdfImportSettings()
    verified_domains: VerifiedDomainSettings = VerifiedDomainSettings()
    sso: SSOSettings = SSOSettings()
    scim: SCIMSettings = SCIMSettings()
    # All your additional application configuration should go either here or in
    # separate file in this submodule.

    model_config = SettingsConfigDict(case_sensitive=False)


settings = Application()

# Session tokens are signed with AUTH_JWT_SECRET and OAuth/SSO state, action
# and SCIM secrets are encrypted with AUTH_AES_HEX_KEY: never run with either
# unset or set to a value published in the repository.
require_secrets(
    "the backend",
    jwt_secrets={"AUTH_JWT_SECRET": settings.auth_settings.JWT_SECRET},
    fernet_keys={"AUTH_AES_HEX_KEY": settings.auth_settings.AES_HEX_KEY},
)
