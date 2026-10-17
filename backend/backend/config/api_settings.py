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
    # This API's address as browsers reach it, the same value as the webapp's
    # NEXT_PUBLIC_API_ENDPOINT_HOST. Unsplash images on forms are stored as
    # <PUBLIC_URL>/images/unsplash/<photo> (services/unsplash_route.py), so
    # respondents load them from us, never from Unsplash.
    PUBLIC_URL: str = "http://localhost:8000/api/v1"
    # GET /images/unsplash/...: requests per client address in each window,
    # and of those, how many may fetch a photo not cached yet.
    IMAGE_PROXY_PER_WINDOW: int = 600
    IMAGE_PROXY_FETCHES_PER_WINDOW: int = 30
    IMAGE_PROXY_WINDOW_SECONDS: int = 60
    # POST /workspaces/{id}/images/import: copies per person in each window.
    IMAGE_IMPORTS_PER_WINDOW: int = 30
    IMAGE_IMPORTS_WINDOW_SECONDS: int = 600

    model_config = SettingsConfigDict(env_prefix="API_")
