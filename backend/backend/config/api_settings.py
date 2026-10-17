from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.version import __version__


class ApiSettings(BaseSettings):
    ENVIRONMENT: str = "local"
    TITLE: str = "[BetterCollected] Forms Integrator Backend API"
    DESCRIPTION: str = "Rest endpoints for better-collected forms integrator API"
    VERSION: str = __version__
    ROOT_PATH: str = "/api/v1"
    HOST: str = ""
    DOMAIN: Optional[str] = ""
    ALLOWED_COLLABORATORS: int = 10
    ALLOWED_WORKSPACES: int = 5
    ENABLE_FORM_CREATION: bool = False
    ENABLE_EXPORT_CSV: bool = False
    CLIENT_URL: str = "http://localhost:3000"
    ENABLE_GOOGLE_PICKER_API: bool = False
    # Proxies whose X-Forwarded-For is believed, besides loopback and the
    # private networks (always trusted): comma-separated addresses or CIDRs.
    # A request from anywhere else is identified by its own address, whatever
    # headers it sends (utils/client_ip.py).
    TRUSTED_PROXIES: str = ""
    # Behind Cloudflare: when the first hop past our proxies is a Cloudflare
    # edge, the client is its CF-Connecting-IP. Off for a deployment that
    # isn't behind Cloudflare. CLOUDFLARE_IPS replaces the built-in ranges
    # (utils/client_ip.CLOUDFLARE_IPS, comma-separated CIDRs).
    TRUST_CLOUDFLARE: bool = True
    CLOUDFLARE_IPS: str = ""
    # Respondents' anonymous page transitions (flow analytics) accepted per
    # client and form in each window; more answer 429 until the window ends.
    FLOW_EVENTS_PER_WINDOW: int = 120
    FLOW_EVENTS_WINDOW_SECONDS: int = 60
    # Public REST API (/api/v1/public/v1): requests per API key in each
    # window; more answer 429 with Retry-After until the window ends. 0 = off.
    PUBLIC_API_REQUESTS_PER_WINDOW: int = 120
    # ...and for all of one workspace's keys together in the same window.
    PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW: int = 600
    PUBLIC_API_WINDOW_SECONDS: int = 60
    # GET /images/unsplash/...: requests per client address in each window,
    # and of those, how many may fetch a photo not cached yet.
    IMAGE_PROXY_PER_WINDOW: int = 600
    IMAGE_PROXY_FETCHES_PER_WINDOW: int = 30
    IMAGE_PROXY_WINDOW_SECONDS: int = 60
    # ...and how many photos everyone together may fetch from Unsplash.
    IMAGE_PROXY_GLOBAL_FETCHES_PER_WINDOW: int = 120
    # POST /workspaces/{id}/images/import: copies per person in each window.
    IMAGE_IMPORTS_PER_WINDOW: int = 30
    IMAGE_IMPORTS_WINDOW_SECONDS: int = 600
    # The builder's op-batch save (POST /workspaces/{id}/forms/{form_id}/ops,
    # services/form_spec/editor_ops.py); 404 while off.
    EDITOR_OPS_SAVE_ENABLED: bool = False

    model_config = SettingsConfigDict(env_prefix="API_")
