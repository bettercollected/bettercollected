"""The inventory: every runtime setting the services read, with its type,
owner (section and readers), secrecy, reload class and guard tier.

``INVENTORY`` holds the keys that may live in the settings store;
``ENV_ONLY_INVENTORY`` documents the keys that are only ever read from the
environment (tier T5: bootstrap, wiring, build arguments, per-service
identity). ``ALIASES`` maps alternative environment names to their key and
``NOT_A_SETTING`` lists names that appear in env files or compose files but
are not read as settings by any service (and why). ``RETIRED`` lists former
settings whose stored rows and environment values are ignored.

Reading the tables:

* readers: ``backend`` (API and the jobs/SCIM/migration entry points that share
  its settings), ``auth``, ``google`` (Google Forms integration),
  ``temporal_worker``, ``actions_executor``, ``jobs`` (queue workers),
  ``admin`` (admin portal process), ``webapp``. The webapp and the actions
  executor read their own environment only; they are listed so an operator
  sees every service a value must reach. The executor runs user-authored code, so
  it is listed for no key material (``AUTH_AES_HEX_KEY``, ``API_KEY``,
  ``AES_HEX_KEY``, the signing and keyset keys): it must not be handed them.
* reload class: ``H`` only for a key every consumer reads at call time (a test
  in ``backend/tests/app/services/test_live_settings_reads.py`` proves it);
  ``R`` otherwise; ``B`` for build arguments. Keys read at import time carry a
  ``TODO_LIVE`` entry naming the file and line.
* default: the code default as the text it would come from; ``None`` when the
  default is empty, derived, or cannot be expressed under the key's own policy
  (a localhost URL). The description then says so.

Pure data: this module imports nothing but the registry. The wiring of the
shipped-secret check lives in ``common.configs.settings_registry``.
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, Iterable, Mapping, Optional, Tuple

from .secret_checks import FormatCheck
from .registry import (
    Registry,
    Reload,
    SecretCheck,
    SettingSpec,
    Tier,
    ValueType,
)

__all__ = [
    "ALIASES",
    "ENV_ONLY_INVENTORY",
    "INVENTORY",
    "NOT_A_SETTING",
    "NOT_A_SETTING_PREFIXES",
    "READERS",
    "RETIRED",
    "TODO_LIVE",
    "all_specs",
    "full_registry",
    "markdown",
]

BACKEND = "backend"
AUTH = "auth"
GOOGLE = "google"
WORKER = "temporal_worker"
EXECUTOR = "actions_executor"
JOBS = "jobs"
ADMIN = "admin"
WEBAPP = "webapp"
TASKS = "tasks"  # the admin task runner (reads the keyset it re-encrypts with)
READERS = frozenset({BACKEND, AUTH, GOOGLE, WORKER, EXECUTOR, JOBS, ADMIN, WEBAPP, TASKS})

T1, T2, T3, T4, T5 = Tier.T1, Tier.T2, Tier.T3, Tier.T4, Tier.T5
H, R, B = Reload.H, Reload.R, Reload.B
STR, INT, BOOL, FLOAT, URL, ENUM = (
    ValueType.STR,
    ValueType.INT,
    ValueType.BOOL,
    ValueType.FLOAT,
    ValueType.URL,
    ValueType.ENUM,
)


def _spec(key, section, readers, description, type=STR, tier=T1, **kw) -> SettingSpec:
    return SettingSpec(
        key,
        section,
        tuple(readers),
        type=type,
        tier=tier,
        description=description,
        **kw,
    )


def _int(key, section, readers, default, lo, hi, description, **kw):
    return _spec(
        key, section, readers, description, INT,
        default=default, min_value=lo, max_value=hi, **kw,
    )


def _float(key, section, readers, default, lo, hi, description, **kw):
    return _spec(
        key, section, readers, description, FLOAT,
        default=default, min_value=lo, max_value=hi, **kw,
    )


def _bool(key, section, readers, default, description, **kw):
    return _spec(key, section, readers, description, BOOL, default=default, **kw)


def _url(key, section, readers, description, default=None, tier=T3, **kw):
    return _spec(key, section, readers, description, URL, tier=tier, default=default, **kw)


def _secret(key, section, readers, description, tier=T2, **kw):
    return _spec(key, section, readers, description, tier=tier, is_secret=True, **kw)


def _text(key, section, readers, description, default=None, tier=T1, **kw):
    return _spec(key, section, readers, description, tier=tier, default=default, **kw)


# --------------------------------------------------------------- server

SERVER: Tuple[SettingSpec, ...] = (
    _bool("DEBUG", "server", (BACKEND, AUTH, GOOGLE), False,
          "Debug mode of the API services (off unless explicitly enabled).", tier=T2),
    _bool("API_DOCS_ENABLED", "server", (BACKEND, AUTH, GOOGLE), False,
          "Serve the interactive API docs (/docs, /redoc) and /openapi.json of the internal APIs.",
          tier=T2),
    _text("API_ENVIRONMENT", "server", (BACKEND, AUTH, GOOGLE),
          "Environment label shown in logs and error reports.", "local", max_length=64),
    _text("API_TITLE", "server", (BACKEND, AUTH), "Title of the generated API documentation.",
          max_length=200),
    _text("API_DESCRIPTION", "server", (BACKEND,), "Description of the generated API documentation.",
          max_length=500),
    _text("API_VERSION", "server", (BACKEND, AUTH, GOOGLE),
          "Version string reported by the API (the code default is the package version).",
          max_length=64),
    _text("API_ROOT_PATH", "server", (BACKEND, AUTH, GOOGLE),
          "URL path prefix every API route is mounted under.", "/api/v1", tier=T2, max_length=64),
    _text("API_HOST", "server", (BACKEND,),
          "Public host name of the API, used for cookie and callback addresses.", tier=T2,
          max_length=253),
    _text("API_DOMAIN", "server", (BACKEND,),
          "Cookie domain of the session cookies.", tier=T2, max_length=253),
    _url("API_CLIENT_URL", "server", (BACKEND, AUTH),
         "Public address of the web app. Code default: http://localhost:3000 (development)."),
    _url("CLIENT_ADMIN_URL", "server", (AUTH,),
         "Public address of the dashboard. Code default: http://localhost:3000 (development)."),
    _text("ORGANIZATION_NAME", "server", (AUTH,), "Organisation name used in outgoing mail.",
          "Better Collected", max_length=100),
    _int("API_ALLOWED_COLLABORATORS", "limits", (BACKEND,), 10, 0, 10000,
         "Collaborators allowed per workspace."),
    _int("API_ALLOWED_WORKSPACES", "limits", (BACKEND,), 5, 0, 10000,
         "Workspaces allowed per account."),
    _bool("ENABLE_SUGGEST_PRICE", "features", (BACKEND,), False,
          "Enables the price suggestion endpoint."),
    _bool("API_ENABLE_FORM_CREATION", "features", (BACKEND,), False,
          "Enables the form creation endpoints."),
    _bool("API_ENABLE_EXPORT_CSV", "features", (BACKEND,), False,
          "Declared for CSV export; no code reads it today."),
    _bool("API_ENABLE_GOOGLE_PICKER_API", "features", (BACKEND,), False,
          "Offers the Google file picker in the import flow."),
    _bool("API_EDITOR_OPS_SAVE_ENABLED", "features", (BACKEND,), False,
          "Whether editor operations are saved server side.", reload_class=H),
    _bool("RESPONSE_VALIDATION_ENFORCE", "features", (BACKEND,), True,
          "Reject answers that break the form's rules (off: log only).", tier=T2),
    _bool("COUPON_ENABLED", "features", (BACKEND,), False, "Enables coupon codes."),
    _int("COUPON_EXPIRY_IN_DAYS", "limits", (BACKEND,), 60, 1, 3650,
         "Days a coupon code stays valid."),
    _text("DEFAULT_WORKSPACE_ID", "workspace", (BACKEND,),
          "Workspace whose forms are offered as templates (a document id).",
          tier=T2, max_length=64),
    _bool("DEFAULT_SHOW_TEMPLATES", "workspace", (BACKEND,), False, "Shows the template gallery."),
    _bool("DEFAULT_SEED_FLOW_TEMPLATES", "workspace", (BACKEND,), True,
          "Seeds the built-in flow templates at startup."),
)

# ----------------------------------------------------- rate limits, retention

RATE = dict(section="rate_limits", readers=(BACKEND,), reload_class=H)
RATE_LIMITS: Tuple[SettingSpec, ...] = (
    _int("API_FLOW_EVENTS_PER_WINDOW", default=120, lo=1, hi=100000,
         description="Flow events accepted per client and form per window.", **RATE),
    _int("API_FLOW_EVENTS_WINDOW_SECONDS", default=60, lo=1, hi=86400,
         description="Length of the flow event window.", **RATE),
    _int("API_PUBLIC_API_REQUESTS_PER_WINDOW", default=120, lo=0, hi=1_000_000,
         description="Public API requests per key per window (0 = off).", **RATE),
    _int("API_PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW", default=600, lo=0, hi=1_000_000,
         description="Public API requests for all keys of a workspace (0 = off).", **RATE),
    _int("API_PUBLIC_API_WINDOW_SECONDS", default=60, lo=1, hi=86400,
         description="Length of the public API window.", **RATE),
    _int("API_IMAGE_PROXY_PER_WINDOW", default=600, lo=0, hi=1_000_000,
         description="Image proxy requests per client per window.", **RATE),
    _int("API_IMAGE_PROXY_FETCHES_PER_WINDOW", default=30, lo=0, hi=1_000_000,
         description="Upstream image fetches per client per window.", **RATE),
    _int("API_IMAGE_PROXY_WINDOW_SECONDS", default=60, lo=1, hi=86400,
         description="Length of the image proxy window.", **RATE),
    _int("API_IMAGE_PROXY_GLOBAL_FETCHES_PER_WINDOW", default=120, lo=0, hi=1_000_000,
         description="Upstream image fetches for all clients per window.", **RATE),
    _int("API_IMAGE_IMPORTS_PER_WINDOW", default=30, lo=0, hi=1_000_000,
         description="Image imports per person per window.", **RATE),
    _int("API_IMAGE_IMPORTS_WINDOW_SECONDS", default=600, lo=1, hi=86400,
         description="Length of the image import window.", **RATE),
    _int("API_EDITOR_OPS_PER_WINDOW", default=300, lo=0, hi=1_000_000,
         description="Editor operation batches per person per window (0 = off).", **RATE),
    _int("API_EDITOR_OPS_WINDOW_SECONDS", default=60, lo=1, hi=86400,
         description="Length of the editor operations window.", **RATE),
    _int("AI_RATE_LIMIT_WINDOW_SECONDS", default=60, lo=1, hi=86400,
         description="Length of the AI request window.", **RATE),
    _int("AI_RATE_LIMIT_PER_USER", default=10, lo=0, hi=100000,
         description="AI requests per person per window (0 = off).", **RATE),
    _int("AI_RATE_LIMIT_PER_WORKSPACE", default=30, lo=0, hi=100000,
         description="AI requests per workspace per window (0 = off).", **RATE),
    _int("AI_RATE_LIMIT_FIX_PER_USER", default=60, lo=0, hi=100000,
         description="Applied review fixes per person per window (0 = off).", **RATE),
    _int("AI_DAILY_REQUEST_BUDGET", default=0, lo=0, hi=10_000_000, tier=T2,
         description="AI requests per workspace per day (0 = unlimited).", **RATE),
    _int("AI_DAILY_TOKEN_BUDGET", default=0, lo=0, hi=2_000_000_000, tier=T2,
         description="AI tokens per workspace per day (0 = unlimited).", **RATE),
    _int("API_FLOW_EVENTS_RETENTION_DAYS", "retention", (BACKEND,), 395, 0, 3650,
         "Days flow events are kept (0 = keep).", tier=T2),
)

# ------------------------------------------------------------- network

NETWORK: Tuple[SettingSpec, ...] = (
    _text("API_TRUSTED_PROXIES", "network", (BACKEND,),
          "Comma separated proxy addresses whose forwarding headers are trusted.",
          tier=T3, format="cidr_list"),
    _bool("API_TRUST_CLOUDFLARE", "network", (BACKEND,), True,
          "Trusts Cloudflare's client address header from Cloudflare ranges.", tier=T3),
    _text("API_CLOUDFLARE_IPS", "network", (BACKEND,),
          "Comma separated Cloudflare ranges (empty: the built-in list).",
          tier=T3, format="cidr_list"),
)

# ------------------------------------------------------- sessions and keys

SESSION: Tuple[SettingSpec, ...] = (
    _int("AUTH_ACCESS_TOKEN_EXPIRY_IN_MINUTES", "session", (BACKEND,), 15, 1, 1440,
         "Minutes an access token is valid.", tier=T2),
    _int("AUTH_REFRESH_TOKEN_EXPIRY_IN_DAYS", "session", (BACKEND,), 30, 1, 365,
         "Days a refresh token is valid.", tier=T2),
    _int("AUTH_REFRESH_REUSE_GRACE_SECONDS", "session", (BACKEND,), 60, 0, 3600,
         "Seconds a used refresh token may be presented again.", tier=T2),
)

KEYS = dict(section="auth_keys", tier=T4)
KEY_MATERIAL: Tuple[SettingSpec, ...] = (
    _secret("AUTH_JWT_SECRET", readers=(BACKEND, AUTH, GOOGLE), format="token",
            description="Signs session tokens; rotated by a task, not edited.", **KEYS),
    # The actions executor runs user-authored code, so it is NOT a reader of any key
    # material: it must not be handed this key (see docs/admin-service.md).
    _secret("AUTH_AES_HEX_KEY", readers=(BACKEND, AUTH, GOOGLE, WORKER), format="fernet",
            retired_readers=(EXECUTOR,),  # rows written before it was dropped still list it
            description="Fernet key for state and secrets; rotated by a task. The workers call it AES_HEX_KEY.",
            **KEYS),
    _secret("AUTH_INTERNAL_NOTIFY_KEY", readers=(BACKEND, AUTH, GOOGLE), format="token",
            description="Shared key for internal service calls; rotated by a task.", **KEYS),
    _secret("TEMPORAL_API_KEY", section="auth_keys", readers=(BACKEND,), tier=T4, format="token",
            description="Key the background workers present to the API (the workers call it API_KEY)."),
    _secret("MASTER_ENCRYPTION_KEYSET", section="auth_keys", readers=(BACKEND, GOOGLE, TASKS), tier=T4,
            format="tink_keyset",
            description="Keyset that encrypts stored responses; changed by a task only."),
    _secret("CUSTOM_DOMAIN_ASSERTION_KEYS", "custom_domain", (BACKEND, WEBAPP), tier=T4,
            format="key_pairs",
            description="Edge signing keys as id:secret pairs; the web app reads its own copy."),
    _secret("CUSTOM_DOMAIN_WEBHOOK_SECRETS", "custom_domain", (BACKEND,), tier=T4,
            format="secret_list",
            description="Webhook subscription secret, current first and previous second."),
)

# ------------------------------------------------------------------ AI

AI: Tuple[SettingSpec, ...] = (
    _spec("AI_DEFAULT_PROVIDER", "ai", (BACKEND,), "Provider used when a request names none.",
          ENUM, tier=T2, default="openai", choices=("openai", "google", "compatible")),
    _url("AI_COMPAT_BASE_URL", "ai", (BACKEND,),
         "Base URL of an OpenAI-compatible endpoint.", internal_ok=True),
    _secret("AI_COMPAT_API_KEY", "ai", (BACKEND,),
            "Key for the compatible endpoint (the code default is the placeholder not-needed)."),
    _text("AI_COMPAT_MODEL", "ai", (BACKEND,), "Model name sent to the compatible endpoint.",
          tier=T2, max_length=200),
    _bool("AI_COMPAT_VISION", "ai", (BACKEND,), False,
          "Whether the compatible model accepts images.", tier=T2),
    _bool("AI_COMPAT_JSON_MODE", "ai", (BACKEND,), True,
          "Whether the compatible endpoint supports JSON mode.", tier=T2),
    _secret("OPENAI_API_KEY", "ai", (BACKEND,), "Key for the OpenAI provider."),
    _text("OPENAI_MODAL", "ai", (BACKEND,),
          "OpenAI model name (the variable name is spelled MODAL in the code).",
          "gpt-5-mini-2025-08-07", tier=T2, max_length=200),
    _secret("GOOGLE_AI_API_KEY", "ai", (BACKEND,), "Key for the Google AI provider."),
    _text("GOOGLE_AI_MODEL", "ai", (BACKEND,), "Google AI model name.",
          "gemini-2.0-flash", tier=T2, max_length=200),
    _float("AI_REQUEST_TIMEOUT_SECONDS", "ai", (BACKEND,), 60, 1, 3600,
           "Provider client request timeout."),
    _float("AI_CALL_TIMEOUT_SECONDS", "ai", (BACKEND,), 120, 1, 3600, "Timeout of one provider call."),
    _float("AI_GENERATION_TIMEOUT_SECONDS", "ai", (BACKEND,), 240, 1, 3600,
           "Timeout of a whole form generation."),
    _float("AI_GAP_FILL_DEADLINE_SECONDS", "ai", (BACKEND,), 120, 1, 3600,
           "Time allowed for the gap filling pass."),
    _int("AI_CLIENT_MAX_RETRIES", "ai", (BACKEND,), 1, 0, 10, "Provider client retries."),
    _int("AI_MAX_OUTPUT_TOKENS_GENERATE", "ai", (BACKEND,), 16000, 1, 200000,
         "Output token cap when generating a form."),
    _int("AI_MAX_OUTPUT_TOKENS_CHAT", "ai", (BACKEND,), 8000, 1, 200000, "Output token cap for chat."),
    _int("AI_MAX_OUTPUT_TOKENS_REVIEW", "ai", (BACKEND,), 8000, 1, 200000,
         "Output token cap for a form review."),
    _int("AI_MAX_OUTPUT_TOKENS_INSIGHTS", "ai", (BACKEND,), 4000, 1, 200000,
         "Output token cap for insights."),
    _int("AI_MAX_OUTPUT_TOKENS_MEMORY", "ai", (BACKEND,), 1000, 1, 200000,
         "Output token cap for memory updates."),
    _int("AI_PROPOSAL_TTL_SECONDS", "ai", (BACKEND,), 3600, 60, 604800,
         "Seconds a proposed change stays applicable."),
)

# --------------------------------------------------- storage and platform

STORAGE: Tuple[SettingSpec, ...] = (
    _secret("AWS_ACCESS_KEY_ID", "storage", (BACKEND,), "Object storage access key id.", tier=T3),
    _secret("AWS_SECRET_ACCESS_KEY", "storage", (BACKEND,), "Object storage secret key.", tier=T3),
    _int("AWS_PRE_SIGNED_URL_EXPIRY", "storage", (BACKEND,), 10, 1, 10080,
         "Lifetime of pre-signed upload and download addresses.", tier=T3),
    _url("AWS_ENDPOINT_URL", "storage", (BACKEND,), "Object storage endpoint.",
         "https://s3.eu-central-1.wasabisys.com"),
    _text("AWS_REGION", "storage", (BACKEND,), "Object storage region.", "eu-central-1",
          tier=T3, max_length=64),
    _text("AWS_BUCKET", "storage", (BACKEND,), "Object storage bucket.", "bettercollected",
          tier=T3, max_length=128),
    _url("AWS_PUBLIC_URL", "storage", (BACKEND,),
         "Public base address of stored files (empty: the endpoint)."),
    _secret("MONGO_URI", "database", (BACKEND, AUTH, GOOGLE),
            "Mongo connection string (code default mongodb://localhost). Each service uses its own value.",
            tier=T3),
    _text("MONGO_DB", "database", (BACKEND, AUTH, GOOGLE),
          "Mongo database name; the code default differs per service.", tier=T3, max_length=64),
)

# ---------------------------------------------------------- SSO and SCIM

SSO = dict(section="sso", tier=T3)
SSO_SPECS: Tuple[SettingSpec, ...] = (
    _bool("SSO_ENABLED", readers=(BACKEND, AUTH, WEBAPP), default=False,
          description="Enables single sign-on (the web app reads its own copy).", **SSO),
    _url("SSO_POLIS_URL", "sso", (BACKEND, AUTH), "Public address of the identity bridge."),
    _url("SSO_POLIS_INTERNAL_URL", "sso", (BACKEND, AUTH),
         "Address of the identity bridge on the internal network.", internal_ok=True),
    _secret("SSO_POLIS_API_KEY", "sso", (BACKEND,), "Key for the identity bridge API.", tier=T3),
    _secret("SSO_POLIS_CLIENT_SECRET", "sso", (AUTH,), "Client secret for the code exchange.", tier=T3),
    _text("SSO_POLIS_PRODUCT", "sso", (BACKEND, AUTH), "Product name in the identity bridge.",
          "bettercollected", tier=T3, max_length=100),
    _text("SSO_SAML_AUDIENCE", "sso", (BACKEND,), "SAML audience.", tier=T3, max_length=500),
    _url("SSO_REDIRECT_URI", "sso", (BACKEND, AUTH), "Address the bridge returns the browser to."),
    _float("SSO_HTTP_TIMEOUT_SECONDS", "sso", (BACKEND, AUTH), 15.0, 1, 120,
           "Timeout of calls to the identity bridge.", tier=T2),
    _int("SSO_MAX_CONNECTIONS_PER_WORKSPACE", "sso", (BACKEND,), 5, 1, 100,
         "Connections a workspace may configure.", tier=T2),
    _int("SSO_STATE_MAX_AGE_SECONDS", "sso", (AUTH,), 600, 30, 3600,
         "Lifetime of the sign-in state.", tier=T2),
    _int("SSO_ASSERTION_MAX_AGE_SECONDS", "sso", (AUTH,), 120, 10, 3600,
         "Lifetime of a sign-in assertion.", tier=T2),
    _url("SCIM_WEBHOOK_URL", "sso", (BACKEND,), "Public address the directory posts events to."),
    _int("SCIM_SIGNATURE_TOLERANCE_SECONDS", "sso", (BACKEND,), 300, 1, 86400,
         "Accepted age of a webhook signature.", tier=T2),
    _int("SCIM_EVENT_RETENTION_SECONDS", "sso", (BACKEND,), 86400, 60, 2_592_000,
         "How long processed webhook events are kept."),
    _int("SCIM_MAX_WEBHOOK_BYTES", "sso", (BACKEND,), 1_000_000, 1024, 50_000_000,
         "Largest accepted webhook body."),
    _text("SCIM_RECONCILE_CRON", "sso", (BACKEND,), "Schedule of the directory reconcile job.",
          "17 3 * * *", tier=T2, max_length=64),
    _int("SCIM_RECONCILE_PAGE_SIZE", "sso", (BACKEND,), 50, 1, 1000, "Page size of the reconcile job."),
    _float("SCIM_RECONCILE_MAX_DEPROVISION_RATIO", "sso", (BACKEND,), 0.2, 0, 1,
           "Largest share of members a reconcile may deprovision.", tier=T2),
    _int("SCIM_RECONCILE_MIN_DEPROVISION", "sso", (BACKEND,), 5, 0, 100000,
         "Deprovisions below this count skip the ratio check.", tier=T2),
    _int("SCIM_ROTATION_GRACE_HOURS", "sso", (BACKEND,), 24, 0, 720,
         "Hours the previous webhook secret stays valid."),
)

# ---------------------------------------------------- mail, billing, OAuth

MAIL = dict(section="mail", tier=T3)
MAIL_BILLING: Tuple[SettingSpec, ...] = (
    _text("MAIL_USER", readers=(AUTH, ADMIN), description="Outgoing mail account name.", **MAIL),
    _secret("MAIL_PASSWORD", "mail", (AUTH, ADMIN), "Outgoing mail account password.", tier=T3),
    _text("MAIL_SMTP_SERVER", readers=(AUTH, ADMIN), format="host",
          description="Outgoing mail server host name.", **MAIL),
    _int("MAIL_SMTP_PORT", "mail", (AUTH, ADMIN), 587, 1, 65535, "Outgoing mail server port.", tier=T3),
    _text("MAIL_SENDER", readers=(AUTH, ADMIN), description="From address of outgoing mail.",
          max_length=320, **MAIL),
    _bool("MAIL_STARTTLS", "mail", (AUTH, ADMIN), True, "Upgrades the connection with STARTTLS.", tier=T3),
    _bool("MAIL_SSL_TLS", "mail", (AUTH, ADMIN), False, "Uses TLS from the start of the connection.", tier=T3),
    _bool("MAIL_USE_CREDENTIALS", "mail", (AUTH, ADMIN), True, "Logs in to the mail server.", tier=T3),
    _bool("MAIL_VALIDATE_CERTS", "mail", (AUTH, ADMIN), True,
          "Verifies the mail server certificate.", tier=T3),
    # The admin portal's own sign-in mail (never the public ``mail`` section).
    # Saving these needs a delivered test mail (see SettingsService.set).
    _text("ADMIN_MAIL_USER", readers=(ADMIN,), section="admin_mail", tier=T3,
          description="Admin sign-in mail account name.", max_length=320),
    _secret("ADMIN_MAIL_PASSWORD", "admin_mail", (ADMIN,),
            "Admin sign-in mail account password.", tier=T3),
    _text("ADMIN_MAIL_SMTP_SERVER", readers=(ADMIN,), section="admin_mail", tier=T3, format="host",
          description="Admin sign-in mail server host name."),
    _int("ADMIN_MAIL_SMTP_PORT", "admin_mail", (ADMIN,), 587, 1, 65535,
         "Admin sign-in mail server port.", tier=T3),
    _text("ADMIN_MAIL_SENDER", readers=(ADMIN,), section="admin_mail", tier=T3, max_length=320,
          description="From address of the admin sign-in mail."),
    _bool("ADMIN_MAIL_STARTTLS", "admin_mail", (ADMIN,), True,
          "Upgrades the admin mail connection with STARTTLS.", tier=T3),
    _bool("ADMIN_MAIL_SSL_TLS", "admin_mail", (ADMIN,), False,
          "Uses TLS from the start of the admin mail connection.", tier=T3),
    _bool("ADMIN_MAIL_USE_CREDENTIALS", "admin_mail", (ADMIN,), True,
          "Logs in to the admin mail server.", tier=T3),
    _bool("ADMIN_MAIL_VALIDATE_CERTS", "admin_mail", (ADMIN,), True,
          "Verifies the admin mail server certificate.", tier=T3),
    _text("MAIL_IMAGE_URL_PREFIXES", readers=(AUTH,), max_length=2000,
          default="https://s3.eu-central-1.wasabisys.com/bettercollected/public/",
          description="Comma separated address prefixes mail images may come from.", **MAIL),
    _text("MAIL_AVATAR_URL_PREFIXES", readers=(AUTH,), max_length=2000,
          default="https://lh3.googleusercontent.com/",
          description="Comma separated address prefixes avatars in mail may come from.", **MAIL),
    _text("STRIPE_PRODUCT_ID", "billing", (AUTH,), "Billing product id.", tier=T3, max_length=100),
    _secret("STRIPE_SECRET", "billing", (AUTH,), "Billing API secret key.", tier=T3),
    _secret("STRIPE_WEBHOOK_SECRET", "billing", (AUTH,), "Billing webhook signing secret.", tier=T3),
    _url("STRIPE_CANCEL_URL", "billing", (AUTH,), "Address after a cancelled checkout."),
    _url("STRIPE_SUCCESS_URL", "billing", (AUTH,), "Address after a completed checkout."),
    _url("STRIPE_RETURN_URL", "billing", (AUTH,), "Address after leaving the billing portal."),
)

GOOGLE_OAUTH: Tuple[SettingSpec, ...] = (
    _text("GOOGLE_CLIENT_ID", "google", (AUTH, GOOGLE, WEBAPP), "Google OAuth client id.",
          tier=T3, max_length=300),
    _text("GOOGLE_PROJECT_ID", "google", (AUTH, GOOGLE), "Google project id.", tier=T3, max_length=200),
    _secret("GOOGLE_CLIENT_SECRET", "google", (AUTH, GOOGLE), "Google OAuth client secret.", tier=T3),
    _url("GOOGLE_AUTH_URI", "google", (AUTH, GOOGLE), "Google authorization endpoint.",
         "https://accounts.google.com/o/oauth2/auth"),
    _url("GOOGLE_TOKEN_URI", "google", (AUTH, GOOGLE), "Google token endpoint.",
         "https://oauth2.googleapis.com/token"),
    _url("GOOGLE_AUTH_PROVIDER_X509_CERT_URL", "google", (AUTH, GOOGLE), "Google certificate endpoint.",
         "https://www.googleapis.com/oauth2/v1/certs"),
    _text("GOOGLE_REDIRECT_URIS", "google", (AUTH, GOOGLE),
          "Allowed OAuth redirect addresses.", tier=T3, max_length=2000),
    _url("GOOGLE_BASIC_AUTH_REDIRECT", "google", (AUTH,), "Redirect address of the basic sign-in."),
    _text("GOOGLE_JAVASCRIPT_ORIGINS", "google", (AUTH, GOOGLE),
          "Allowed browser origins for Google sign-in.", tier=T3, max_length=2000),
    _text("GOOGLE_CLIENT_TYPE", "google", (GOOGLE,), "Google OAuth client type.", "web", tier=T3,
          max_length=32),
    _text("GOOGLE_SCOPES", "google", (GOOGLE,), "Scopes requested for form import.", tier=T3,
          max_length=2000,
          default="openid https://www.googleapis.com/auth/userinfo.profile "
          "https://www.googleapis.com/auth/userinfo.email "
          "https://www.googleapis.com/auth/forms.body.readonly "
          "https://www.googleapis.com/auth/forms.responses.readonly"),
    _text("GOOGLE_SHEET_SCOPE", "google", (GOOGLE,), "Scopes requested for sheet export.", tier=T3,
          max_length=2000,
          default="https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive"),
    _url("GOOGLE_SHEET_REDIRECT_URL", "google", (GOOGLE,),
         "Redirect address of the sheet export flow. Code default: http://localhost:3000/integrations/google/callback."),
    _text("GOOGLE_API_SERVICE_NAME", "google", (GOOGLE,), "Google API service name.", "drive", max_length=64),
    _text("GOOGLE_API_VERSION", "google", (GOOGLE,), "Google API version.", "v2", max_length=16),
    _url("GOOGLE_REVOKE_CREDENTIALS_URL", "google", (GOOGLE,), "Google token revocation endpoint.",
         "https://oauth2.googleapis.com/revoke"),
    _spec("GOOGLE_FORMS_IMPORT", "google", (BACKEND, GOOGLE),
          "Google Forms import: on; readonly (imported data stays, no import, sync or call to "
          "Google: 403); off (410, the service is never called).",
          ENUM, tier=T2, default="on", choices=("on", "readonly", "off")),
    _url("AUTH_CALLBACK_URI", "google", (BACKEND,),
         "OAuth callback address (the code default is the auth address plus /auth/callback)."),
)

# ----------------------------------------------------- services and add-ons

SERVICES: Tuple[SettingSpec, ...] = (
    _url("EVENT_WEBHOOK_URL", "webhooks", (BACKEND,), "Address platform events are posted to."),
    _bool("EVENT_WEBHOOK_ENABLED", "webhooks", (BACKEND,), False,
          "Posts platform events to the webhook address.", tier=T3),
    _url("UMAMI_URL", "analytics", (BACKEND,), "Address of the analytics server.", internal_ok=True),
    _text("UMAMI_USERNAME", "analytics", (BACKEND,), "Analytics account name.", tier=T2, max_length=200),
    _secret("UMAMI_PASSWORD", "analytics", (BACKEND,), "Analytics account password."),
    _text("UMAMI_WEBSITE_ID", "analytics", (BACKEND, WEBAPP), "Analytics website id.", tier=T2,
          max_length=100),
    _text("UMAMI_WEBSITE_NAME", "analytics", (BACKEND,), "Analytics website name.", "BetterCollected",
          max_length=100),
    _secret("SENTRY_DSN", "monitoring", (BACKEND, AUTH, GOOGLE), "Error report destination."),
    _bool("SENTRY_DEBUG", "monitoring", (BACKEND, AUTH, GOOGLE), False, "Verbose error reporter."),
    _secret("UNSPLASH_ACCESS_KEY", "integrations", (BACKEND, WEBAPP),
            "Photo library access key (read by the webapp's photo picker; the backend does not use it and starts without it)."),
    _url("UNSPLASH_BASE_URL", "integrations", (BACKEND,), "Photo library API address.",
         "https://api.unsplash.com"),
    _int("UNSPLASH_PER_PAGE", "integrations", (BACKEND,), 10, 1, 100, "Photos per search page."),
    _url("CUSTOM_DOMAIN_API_URL", "custom_domain", (BACKEND,), "Address of the custom domain service."),
    _secret("CUSTOM_DOMAIN_API_CREDENTIAL", "custom_domain", (BACKEND,),
            "Credential for the custom domain service.", tier=T3),
    _text("CUSTOM_DOMAIN_APPLICATION_ID", "custom_domain", (BACKEND, WEBAPP),
          "Application id at the custom domain service.", tier=T3, max_length=200),
    _text("HTTPS_CERT_API_HOST", "custom_domain", (BACKEND,),
          "Address of the legacy certificate server.", tier=T3, max_length=253),
    _secret("HTTPS_CERT_API_KEY", "custom_domain", (BACKEND,), "Key of the legacy certificate server.", tier=T3),
    _text("HTTPS_CERT_API_UPSTREAM", "custom_domain", (BACKEND,),
          "Upstream the legacy certificate server points domains at.", tier=T3, max_length=253),
    _float("VERIFIED_DOMAINS_DNS_TIMEOUT_S", "domains", (BACKEND,), 5.0, 0.5, 60, "DNS lookup timeout."),
    _text("VERIFIED_DOMAINS_NAMESERVERS", "domains", (BACKEND,),
          "Comma separated resolver IP addresses (empty: system resolvers).", tier=T3, max_length=500,
          format="ip_list"),
    _int("VERIFIED_DOMAINS_LOSS_AFTER_FAILED_CHECKS", "domains", (BACKEND,), 3, 1, 100,
         "Failed checks before a domain counts as lost."),
    _int("VERIFIED_DOMAINS_RECHECK_INTERVAL_HOURS", "domains", (BACKEND,), 24, 1, 720,
         "Hours between checks of a verified domain."),
    _int("VERIFIED_DOMAINS_MAX_PER_WORKSPACE", "domains", (BACKEND,), 20, 1, 1000,
         "Domains a workspace may verify."),
    _text("VERIFIED_DOMAINS_RESERVED", "domains", (BACKEND,),
          "Comma separated domains no workspace may claim.", tier=T2, max_length=4000),
)

PDF = dict(section="pdf_import", readers=(BACKEND,))
PDF_IMPORT: Tuple[SettingSpec, ...] = (
    _int("PDF_IMPORT_MAX_BYTES", default=15 * 1024 * 1024, lo=1024, hi=500 * 1024 * 1024,
         description="Largest file accepted.", **PDF),
    _int("PDF_IMPORT_MAX_PAGES", default=30, lo=1, hi=1000, description="Most pages accepted.", **PDF),
    _int("PDF_IMPORT_IMPORTS_PER_WORKSPACE_PER_DAY", default=10, lo=0, hi=100000,
         description="Imports per workspace per day.", **PDF),
    _int("PDF_IMPORT_CONCURRENT_IMPORTS_PER_WORKSPACE", default=1, lo=1, hi=100,
         description="Imports a workspace may run at once.", **PDF),
    _int("PDF_IMPORT_MAX_IMAGE_PIXELS", default=60_000_000, lo=1_000_000, hi=1_000_000_000,
         description="Most pixels of a photographed form.", **PDF),
    _int("PDF_IMPORT_SANDBOX_TIMEOUT_S", default=120, lo=5, hi=3600, description="Sandbox time limit.", **PDF),
    _int("PDF_IMPORT_SANDBOX_MEMORY_MB", default=1536, lo=128, hi=65536,
         description="Sandbox memory limit in megabytes.", **PDF),
    _int("PDF_IMPORT_MAX_PARALLEL_SANDBOXES", default=2, lo=1, hi=64,
         description="Sandboxes running at once.", **PDF),
    _int("PDF_IMPORT_MAX_RESULT_BYTES", default=16 * 1024 * 1024, lo=1024, hi=500 * 1024 * 1024,
         description="Largest sandbox result accepted.", **PDF),
    _text("PDF_IMPORT_OPENAI_MODEL", "pdf_import", (BACKEND,), "Model used to read imported forms.",
          "gpt-6-luna", tier=T2, max_length=200),
    _int("PDF_IMPORT_RENDER_MAX_SIDE", default=1600, lo=200, hi=8000,
         description="Longest side of rendered pages in pixels.", **PDF),
    _int("PDF_IMPORT_HEARTBEAT_S", default=30, lo=1, hi=3600,
         description="Seconds between import heartbeats (stale-after must be at least four times this).", **PDF),
    _int("PDF_IMPORT_STALE_AFTER_S", default=600, lo=4, hi=86400,
         description="Seconds without a heartbeat before an import counts as stale.", **PDF),
    _text("PDF_IMPORT_STALE_SWEEP_CRON", "pdf_import", (BACKEND,), "Schedule of the stale import sweep.",
          "*/10 * * * *", tier=T2, max_length=64),
)

INVENTORY: Tuple[SettingSpec, ...] = (
    SERVER + RATE_LIMITS + NETWORK + SESSION + KEY_MATERIAL + AI + STORAGE + SSO_SPECS
    + MAIL_BILLING + GOOGLE_OAUTH + SERVICES + PDF_IMPORT
)

# Keys read at import time (or captured when the container is built): they stay
# R until the consumer reads them at call time. Value: file and line.
TODO_LIVE: Dict[str, str] = {
    "API_FLOW_EVENTS_RETENTION_DAYS": "backend/backend/app/services/flow_event_service.py:117",
    "PDF_IMPORT_STALE_SWEEP_CRON": "backend/backend/jobs/tasks.py:109",
    "SCIM_RECONCILE_CRON": "backend/backend/jobs/tasks.py:125",
    "API_ROOT_PATH": "backend/backend/app/asgi.py:201",
    "API_DOCS_ENABLED": "backend/backend/app/asgi.py:201",
    "AWS_ACCESS_KEY_ID": "backend/backend/app/container.py:533",
    "AWS_SECRET_ACCESS_KEY": "backend/backend/app/container.py:534",
}

# ------------------------------------------------------- environment only

_DB = (BACKEND, AUTH, GOOGLE, JOBS, ADMIN)
_APM = (BACKEND, AUTH, GOOGLE, WORKER, EXECUTOR, WEBAPP)
ENV_ONLY_INVENTORY: Tuple[SettingSpec, ...] = (
    _secret("DATABASE_URL", "database", _DB + (EXECUTOR,), "Postgres connection string.", tier=T5),
    _bool("DB_AUTO_MIGRATE", "database", (BACKEND, AUTH, GOOGLE), False,
          "Applies pending schema migrations at startup.", tier=T5),
    _float("DB_AUTO_MIGRATE_LOCK_WAIT_SECONDS", "database", (BACKEND, AUTH, GOOGLE), None, 0, 3600,
           "Seconds to wait for the migration lock.", tier=T5),
    _spec("DB_READ_SOURCE", "database", (BACKEND, AUTH, GOOGLE),
          "Where reads come from (DB_READ_SOURCE__<table> overrides one table).",
          ENUM, tier=T5, default="mongo", choices=("mongo", "postgres")),
    _spec("DB_WRITE_MODE", "database", (BACKEND, AUTH, GOOGLE),
          "Which stores writes go to (DB_WRITE_MODE__<table> overrides one table).",
          ENUM, tier=T5, default="mongo",
          choices=("mongo", "dual", "postgres_primary_dual", "postgres")),
    _float("DB_SHADOW_READ_SAMPLE", "database", (BACKEND, AUTH, GOOGLE), 0.0, 0, 1,
           "Share of reads compared against the other store.", tier=T5),
    _text("DB_DISCARD_UNIMPORTED_MONGO_DATA", "database", (BACKEND, JOBS),
          "Starts despite Mongo data never imported for these Postgres-only groups "
          "(all, or a comma-separated list); that data is left behind.", tier=T5),
    _int("DB_POOL_SIZE", "database", _DB, 5, 1, 200, "Connection pool size.", tier=T5),
    _int("DB_MAX_OVERFLOW", "database", _DB, 5, 0, 200, "Extra connections above the pool.", tier=T5),
    _int("DB_POOL_TIMEOUT_S", "database", _DB, 10, 1, 600, "Seconds to wait for a connection.", tier=T5),
    _int("DB_STATEMENT_TIMEOUT_MS", "database", _DB, 30_000, 100, 3_600_000,
         "Statement time limit.", tier=T5),
    _int("DB_LOCK_TIMEOUT_MS", "database", _DB, 5_000, 100, 3_600_000, "Lock wait limit.", tier=T5),
    _int("DB_IDLE_IN_TRANSACTION_MS", "database", _DB, 60_000, 1000, 3_600_000,
         "Idle in transaction limit.", tier=T5),
    _int("DB_MIRROR_TIMEOUT_MS", "database", _DB, 2_000, 100, 600_000, "Mirror write time limit.", tier=T5),
    _bool("DB_ECHO", "database", _DB, False, "Logs every statement.", tier=T5),
    _spec("JOBS_BACKEND", "jobs", (BACKEND, JOBS, EXECUTOR), "Queue backend for background work.",
          ENUM, tier=T5, default="temporal", choices=("temporal", "postgres")),
    _text("JOBS_QUEUES", "jobs", (JOBS,), "Comma separated queues a jobs worker serves.", tier=T5),
    _int("JOBS_CONCURRENCY", "jobs", (JOBS, EXECUTOR), 4, 1, 256, "Jobs run at once per worker.", tier=T5),
    _int("JOBS_POOL_MIN", "jobs", (JOBS,), 1, 1, 100, "Minimum queue connections.", tier=T5),
    _int("JOBS_POOL_MAX", "jobs", (JOBS, EXECUTOR), 4, 1, 100, "Maximum queue connections.", tier=T5),
    _secret("SETTINGS_MASTER_KEY", "bootstrap", (BACKEND, ADMIN), "Master key of the settings store.", tier=T5),
    _secret("SETTINGS_MASTER_KEY_PREVIOUS", "bootstrap", (BACKEND, ADMIN),
            "Previous master key, set only while rotating.", tier=T5),
    _text("SETTINGS_STORE", "bootstrap", (BACKEND, ADMIN), "Whether the settings store is used.", tier=T5),
    _text("PLATFORM_ADMIN_EMAILS", "bootstrap", (BACKEND, AUTH),
          "Comma separated emails granted platform admin on verified sign-in.", tier=T5),
    _text("DOTENV_PATH", "bootstrap", (BACKEND, AUTH, GOOGLE), "Path of the env file to load.", tier=T5),
    _int("PORT", "bootstrap", (BACKEND, AUTH, GOOGLE), 8000, 1, 65535, "Listen port.", tier=T5),
    _text("TEMPLATE_FOLDER", "bootstrap", (AUTH,), "Folder of the mail templates.",
          "auth/app/templates", tier=T5),
    _text("PROJECT_NAME", "bootstrap", (GOOGLE,), "Name of the Google Forms integration API.",
          "googleform", tier=T5),
    _text("DOCS_URL", "bootstrap", (GOOGLE,), "Path the Google Forms integration serves its API docs at.",
          "/docs", tier=T5),
    _text("VERSION", "bootstrap", (GOOGLE,),
          "Version of the Google Forms integration (the code default is the package version).", tier=T5),
    _secret("ADMIN_DATABASE_URL", "admin", (ADMIN,), "Postgres connection string of the admin portal.", tier=T5),
    _int("ADMIN_PORT", "admin", (ADMIN,), None, 1, 65535, "Port the admin portal is reached on.", tier=T5),
    _int("ADMIN_LISTEN_PORT", "admin", (ADMIN,), None, 1, 65535, "Port the admin process listens on.", tier=T5),
    _text("ADMIN_BIND_HOST", "admin", (ADMIN,), "Address the admin process binds to.",
          "127.0.0.1", tier=T5),
    _text("ADMIN_ALLOWED_IPS", "admin", (ADMIN,), "Addresses allowed to reach the admin portal.",
          "127.0.0.1/32", tier=T5),
    _text("ADMIN_ALLOWED_HOSTS", "admin", (ADMIN,), "Host names the admin portal answers to.", tier=T5),
    _text("ADMIN_EDGE_GATEWAY", "admin", (ADMIN,), "Address of the edge in front of the portal.", tier=T5),
    _text("ADMIN_TRUSTED_PROXIES", "admin", (ADMIN,), "Proxies trusted by the admin portal.", tier=T5),
    _text("ADMIN_DB_RUNTIME_ROLE", "admin", (ADMIN,), "Database role the admin portal runs as.",
          "bc_admin", tier=T5),
    _secret("TASKS_DATABASE_URL", "admin", (ADMIN,),
            "Postgres connection string of the data task runner (role bc_tasks).", tier=T5),
    _bool("ADMIN_TASKS_SELFTEST", "admin", (ADMIN,), False,
          "Registers the runner's test-only tasks (never in production).", tier=T5),
    _int("ADMIN_TASKS_MAX_REQUEST_AGE_HOURS", "admin", (ADMIN,), 24, 1, 24,
         "Hours after which the runner refuses a queued task request as expired (cap 24).",
         tier=T5),
    _bool("ADMIN_LOOPS_ENABLED", "admin", (ADMIN,), True,
          "Runs the admin portal's background loops (notification mail, retention, integrity checks).",
          tier=T5),
    _int("ADMIN_NOTIFY_INTERVAL_SECONDS", "admin", (ADMIN,), 15, 1, 3600,
         "Seconds between passes over the admin notification outbox.", tier=T5),
    _int("ADMIN_NOTIFY_MAX_PER_MINUTE", "admin", (ADMIN,), 30, 1, 600,
         "Most admin notification mails sent per minute.", tier=T5),
    _int("ADMIN_RETENTION_INTERVAL_SECONDS", "admin", (ADMIN,), 3600, 10, 86400,
         "Seconds between the admin portal's retention passes.", tier=T5),
    _int("ADMIN_INTEGRITY_INTERVAL_SECONDS", "admin", (ADMIN,), 600, 10, 86400,
         "Seconds between the admin portal's settings integrity checks.", tier=T5),
    _bool("PDF_IMPORT_REQUIRE_ISOLATED_SANDBOX", "pdf_import", (BACKEND,), False,
          "Refuses imports unless the isolated sandbox is available.", tier=T5),
    _text("PDF_IMPORT_SANDBOX_SOCKET", "pdf_import", (BACKEND,),
          "Address of the isolated sandbox service.", tier=T5),
    _int("DOC_SANDBOX_PARALLEL", "pdf_import", (BACKEND,), 2, 1, 64,
         "Parallel documents inside the sandbox service.", tier=T5),
    _int("DOC_SANDBOX_MAX_DOCUMENT_BYTES", "pdf_import", (BACKEND,), 32 * 1024 * 1024, 1024,
         1_000_000_000, "Largest document the sandbox service accepts.", tier=T5),
    _url("AUTH_BASE_URL", "services", (BACKEND,),
         "Address of the auth service. Code default: http://localhost:8001/api/v1.", tier=T5),
    _url("AUTH_SERVER_URL", "services", (GOOGLE,), "Address of the auth service.",
         "http://auth:8000/api/v1", tier=T5, internal_ok=True),
    _text("TEMPORAL_SERVER_URI", "services", (BACKEND,), "Workflow server address (host:port).",
          "localhost:7233", tier=T5),
    _text("TEMPORAL_NAMESPACE", "services", (BACKEND,), "Workflow namespace.", "default", tier=T5),
    _text("TEMPORAL_TEMPLATE_PREVIEW_QUEUE", "services", (BACKEND,), "Queue of template previews.",
          "template_preview_queue", tier=T5),
    _text("TEMPORAL_WORKER_QUEUE", "services", (BACKEND,), "Queue of the default worker.", "default", tier=T5),
    _text("TEMPORAL_ACTION_QUEUE", "services", (BACKEND,), "Queue of the actions executor.", "actions", tier=T5),
    _text("TEMPORAL_CSV_QUEUE", "services", (BACKEND,), "Queue of the CSV worker.", "csv_worker", tier=T5),
    _text("TEMPORAL_SERVER_URL", "services", (WORKER, EXECUTOR), "Workflow server address (host:port).",
          "localhost:7233", tier=T5),
    _text("NAMESPACE", "services", (WORKER, EXECUTOR), "Workflow namespace of the worker.", "default", tier=T5),
    _text("SERVER_URL", "services", (WORKER, EXECUTOR), "Address of the API the worker calls.",
          "http://backend:8000/api/v1", tier=T5),
    _text("BACKEND_URL", "services", (EXECUTOR,), "Public API address used in action links.",
          "http://localhost:8000/api/v1", tier=T5),
    _text("FRONTEND_URL", "services", (EXECUTOR,), "Public web address used in action links.",
          "http://localhost:3000", tier=T5),
    _secret("API_KEY", "services", (WORKER,),
            "Key presented to the API; the same value as TEMPORAL_API_KEY. Not for the actions executor.",
            tier=T5),
    _secret("AES_HEX_KEY", "services", (WORKER,),
            "Fernet key of the workers; the same value as AUTH_AES_HEX_KEY. Not for the actions executor.",
            tier=T5),
    _text("WORKER_QUEUE", "services", (WORKER, EXECUTOR),
          "Queue the worker serves (code default: default for the worker, actions for the executor).",
          tier=T5),
    _int("WORKERS", "services", (WORKER, EXECUTOR), 10, 1, 1000, "Workflow tasks run at once.", tier=T5),
    _text("COOKIE_DOMAIN", "services", (WORKER, EXECUTOR), "Cookie domain the workers use.",
          "localhost", tier=T5),
    _int("MAX_THREAD_POOL_EXECUTORS", "services", (GOOGLE, WORKER, EXECUTOR), None, 1, 10000,
         "Thread pool size (code default 150 for google, 20 for the workers).", tier=T5),
    _text("ELASTIC_APM_SERVICE_NAME", "monitoring", _APM, "Name this service reports under.", tier=T5),
    _url("ELASTIC_APM_SERVER_URL", "monitoring", _APM, "Performance monitoring server.", tier=T5),
    _secret("ELASTIC_APM_API_KEY", "monitoring", _APM, "Performance monitoring key.", tier=T5),
    _secret("ELASTIC_APM_SECRET_TOKEN", "monitoring", (WEBAPP,),
            "Legacy performance monitoring token.", tier=T5),
    _text("ELASTIC_APM_ENVIRONMENT", "monitoring", (BACKEND, AUTH, GOOGLE, EXECUTOR, WEBAPP),
          "Environment label of the monitoring reports.", tier=T5),
    _bool("ELASTIC_APM_ENABLED", "monitoring", (WORKER, EXECUTOR), False,
          "Turns the worker monitoring on.", tier=T5),
    _text("NEXT_PUBLIC_API_ENDPOINT_HOST", "webapp", (WEBAPP,),
          "API address compiled into the web app (build argument).", tier=T5, reload_class=B),
    _text("NEXT_PUBLIC_NODE_ENV", "webapp", (WEBAPP,),
          "Environment label compiled into the web app (build argument).", tier=T5, reload_class=B),
    _text("NEXT_PUBLIC_DASHBOARD_DOMAIN", "webapp", (WEBAPP,),
          "Dashboard domain used by the frame header (build argument).", tier=T5, reload_class=B),
    _text("NEXT_PUBLIC_APP_URL", "webapp", (WEBAPP,),
          "Public address compiled into the web app (build argument).", tier=T5, reload_class=B),
    _text("BASE_DEPLOY_PATH", "webapp", (WEBAPP,),
          "Path the web app is served under (build argument).", tier=T5, reload_class=B),
    _text("API_ENDPOINT_HOST", "webapp", (WEBAPP,), "API address the web app server calls publicly.", tier=T5),
    _text("INTERNAL_DOCKER_API_ENDPOINT_HOST", "webapp", (WEBAPP,),
          "API address the web app server calls inside the network.", tier=T5),
    _text("HTTP_SCHEME", "webapp", (WEBAPP,), "Scheme (with ://) of the public addresses.", tier=T5),
    _text("FORM_DOMAIN", "webapp", (WEBAPP,), "Domain forms are served on.", tier=T5),
    _text("DASHBOARD_DOMAIN", "webapp", (WEBAPP,), "Domain the dashboard is served on.", tier=T5),
    _text("FORM_PRIVACY_POLICY_URL", "webapp", (WEBAPP,), "Privacy policy address shown on forms.", tier=T5),
    _text("GOOGLE_PICKER_API_KEY", "webapp", (WEBAPP,), "Browser key of the Google file picker.", tier=T5),
    _text("UMAMI_SCRIPT_URL", "webapp", (WEBAPP,), "Address of the analytics script.", tier=T5),
    _spec("CUSTOM_DOMAIN_ASSERTION_MODE", "webapp", (WEBAPP,),
          "Whether a custom domain request must carry an assertion.",
          ENUM, tier=T5, default="required", choices=("required", "optional")),
    _secret("CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN", "webapp", (WEBAPP,),
            "Token proving ownership of the origin.", tier=T5),
)

# Other names for a key (the first name a service reads wins).
ALIASES: Dict[str, str] = {
    "CLIENT_URL": "API_CLIENT_URL",
    "TRUSTED_PROXIES": "API_TRUSTED_PROXIES",
    "VERIFIED_DOMAINS_PLATFORM_ADMIN_EMAILS": "PLATFORM_ADMIN_EMAILS",
    # the task-runner compose service's names for the data stores and the keyset
    "TASK_RUNNER_DATABASE_URL": "DATABASE_URL",
    "TASK_RUNNER_GOOGLE_DATABASE_URL": "DATABASE_URL",
    "GOOGLE_DATABASE_URL": "DATABASE_URL",
    "TASK_RUNNER_MONGO_URI": "MONGO_URI",
    "TASK_RUNNER_MONGO_DB": "MONGO_DB",
    "TASK_RUNNER_KEYSET": "MASTER_ENCRYPTION_KEYSET",
}

# Names in env files, compose files or code that no service reads as a setting.
NOT_A_SETTING: Dict[str, str] = {
    "GOOGLE_MONGO_DB": "the Google integration's Mongo database, read by the keyset rotation tasks and script",
    "TASK_RUNNER_GOOGLE_MONGO_DB": "the task-runner compose service's name for GOOGLE_MONGO_DB",
    "NODE_ENV": "set by the Node.js tooling",
    "NEXT_PUBLIC_APP_VERSION": "build-time version, set by the image build (never stored)",
    "OAUTHLIB_INSECURE_TRANSPORT": "read by the oauthlib library",
    "OAUTHLIB_RELAX_TOKEN_SCOPE": "read by the oauthlib library",
    "BC_RENDER_MAX_SIDE": "set by the import runner for its own sandbox child",
    "STRIPE_REDIRECT_URL": "compose interpolation expanded into the STRIPE_*_URL keys",
    "ENABLE_COMMAND_FORM_BUILDERS": "listed in the deployment env file; no service reads it",
    "ENABLE_FORM_BUILDER": "listed in the deployment env file; no service reads it",
    "SCHEDULAR_INTERVAL_MINUTES": "listed in an env example; no service reads it",
    "TEMPLATE_PREDEFINED_WORKSPACE_ID": "listed in an env example; no service reads it",
    "VIRTUAL_HOST_1": "read by the reverse proxy image, not by a service",
    "APP_POSTGRES_PASSWORD": "database role password used by the deploy scripts",
    "POLIS_IMAGE": "compose image selection",
    "POLIS_EGRESS_SUBNET": "compose subnet of the identity bridge's egress network",
    "POLIS_CLIENT_SECRET_VERIFIER": "read by the identity bridge container",
    "POLIS_DB_ENCRYPTION_KEY": "read by the identity bridge container",
    "POLIS_NEXTAUTH_SECRET": "read by the identity bridge container",
    "MOCK_SAML_IMAGE": "compose image selection for the development identity provider",
    "SANDBOX_UID": "compose build argument of the local sandbox",
    "SANDBOX_GID": "compose build argument of the local sandbox",
    "UMAMI_APP_SECRET": "read by the analytics container",
}


# Keys that were settings once. A stored row of one is ignored (never applied,
# never reported as refused) and an environment value of one is read by no
# service, so a stack that still holds them keeps working; the rows stay in the
# store until a later release prunes them.
_TYPEFORM_GONE = "Typeform integration, removed in 4.1; ignored"
_BREVO_GONE = "marketing tracker (Brevo), removed; ignored"
RETIRED: Dict[str, str] = {
    "TYPEFORM_API_URI": _TYPEFORM_GONE,
    "TYPEFORM_AUTH_URI": _TYPEFORM_GONE,
    "TYPEFORM_BASIC_REDIRECT_URI": _TYPEFORM_GONE,
    "TYPEFORM_BASIC_SCOPE": _TYPEFORM_GONE,
    "TYPEFORM_CLIENT_ID": _TYPEFORM_GONE,
    "TYPEFORM_CLIENT_SECRET": _TYPEFORM_GONE,
    "TYPEFORM_ENABLED": _TYPEFORM_GONE,
    "TYPEFORM_REDIRECT_URI": _TYPEFORM_GONE,
    "TYPEFORM_SCOPE": _TYPEFORM_GONE,
    "TYPEFORM_TOKEN_URI": _TYPEFORM_GONE,
    "BREVO_CONTACTS_API_KEY": _BREVO_GONE,
    "BREVO_TRACKER_API_URL": _BREVO_GONE,
    "BREVO_TRACKER_KEY": _BREVO_GONE,
}


# Name prefixes that are never settings (database role passwords of the deploy scripts).
NOT_A_SETTING_PREFIXES: Tuple[str, ...] = ("BC_",)


def all_specs() -> Tuple[SettingSpec, ...]:
    return INVENTORY + ENV_ONLY_INVENTORY


def full_registry(
    secret_problems: Optional[SecretCheck] = None,
    format_checks: Optional[Mapping[str, FormatCheck]] = None,
) -> Registry:
    """A registry of every storable key (``ENV_ONLY_INVENTORY`` is not stored)."""
    return Registry(
        INVENTORY, secret_problems=secret_problems, format_checks=format_checks, retired=RETIRED
    )


# ---------------------------------------------------------------- markdown


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _type(spec: SettingSpec) -> str:
    parts = [spec.type.value]
    if spec.type is ValueType.ENUM:
        parts.append("/".join(spec.choices))
    if spec.min_value is not None or spec.max_value is not None:
        lo = "" if spec.min_value is None else f"{spec.min_value:g}"
        hi = "" if spec.max_value is None else f"{spec.max_value:g}"
        parts.append(f"{lo}..{hi}")
    if spec.max_length is not None:
        parts.append(f"max {spec.max_length}")
    if spec.format:
        parts.append(spec.format)
    if spec.internal_ok:
        parts.append("internal ok")
    return " ".join(parts)


def markdown() -> str:
    """The committed ``docs/settings-inventory.md``; ``--markdown`` prints it."""
    lines = [
        "# Settings inventory",
        "",
        "<!-- Generated by `python -m common.settings.inventory --markdown`; do not edit. -->",
        "",
        "A registry of every runtime setting with its type, owner, secrecy, reload class and",
        "guard tier. The source is `common/common/settings/inventory.py`; a test keeps this",
        "file current.",
        "",
        "Reload class: `H` read live (no restart), `R` restart, `B` build argument.",
        "Tiers: T1 audit only, T2 step-up and notify, T3 typed confirmation and URL check,",
        "T4 key material changed by a task only, T5 environment only (never stored).",
        "Secrets show no default. The webapp and the actions executor read their own",
        "environment, whatever the tier.",
        "",
    ]
    header = "| Key | Section | Readers | Type | Secret | Reload | Tier | Default |"
    divider = "|---|---|---|---|---|---|---|---|"
    for title, specs in (
        ("Stored settings", INVENTORY),
        ("Environment only", ENV_ONLY_INVENTORY),
    ):
        lines += [f"## {title}", "", header, divider]
        for s in sorted(specs, key=lambda s: (s.section, s.key)):
            if s.is_secret or s.default is None:
                default = ""
            elif isinstance(s.default, bool):
                default = f"`{str(s.default).lower()}`"
            else:
                default = f"`{_cell(s.default)}`"
            lines.append(
                f"| `{s.key}` | {s.section} | {', '.join(s.readers)} | {_cell(_type(s))} "
                f"| {'yes' if s.is_secret else ''} | {s.reload_class.value} | {s.tier.value} "
                f"| {default} |"
            )
        lines.append("")
    lines += ["## Other names", "", "| Name | Means |", "|---|---|"]
    lines += [f"| `{a}` | `{k}` |" for a, k in sorted(ALIASES.items())]
    lines += ["", "## Not settings", "", "| Name | Why |", "|---|---|"]
    lines += [f"| `{n}` | {_cell(w)} |" for n, w in sorted(NOT_A_SETTING.items())]
    lines += [f"| `{p}*` | database role passwords of the deploy scripts |" for p in NOT_A_SETTING_PREFIXES]
    lines += ["", "## Retired", "", "| Name | Why |", "|---|---|"]
    lines += [f"| `{n}` | {_cell(w)} |" for n, w in sorted(RETIRED.items())]
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m common.settings.inventory")
    parser.add_argument("--markdown", action="store_true", help="print the inventory table")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.markdown:
        parser.print_usage(sys.stderr)
        return 2
    sys.stdout.write(markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
