"""Hot settings whose consumers are proven to read them at call time.

A key marked class H in the registry is only hot if the code that enforces it
reads it through ``live()`` on every call. ``LIVE_PROVEN`` lists the keys whose
consumers do, each pinned by a test in
``backend/tests/app/services/test_live_settings_reads.py`` that changes the
value in the loader's snapshot and checks the consumer's next call. The
loader reports ``restart_pending`` when an H key outside this set changes, so a
new H key cannot silently look applied; ``common/tests/settings`` requires
every H key in the registry to be listed here.
"""

LIVE_PROVEN = frozenset(
    {
        "API_FLOW_EVENTS_PER_WINDOW",
        "API_FLOW_EVENTS_WINDOW_SECONDS",
        "API_PUBLIC_API_REQUESTS_PER_WINDOW",
        "API_PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW",
        "API_PUBLIC_API_WINDOW_SECONDS",
        "API_IMAGE_PROXY_PER_WINDOW",
        "API_IMAGE_PROXY_FETCHES_PER_WINDOW",
        "API_IMAGE_PROXY_WINDOW_SECONDS",
        "API_IMAGE_PROXY_GLOBAL_FETCHES_PER_WINDOW",
        "API_IMAGE_IMPORTS_PER_WINDOW",
        "API_IMAGE_IMPORTS_WINDOW_SECONDS",
        "API_EDITOR_OPS_SAVE_ENABLED",
        "API_EDITOR_OPS_PER_WINDOW",
        "API_EDITOR_OPS_WINDOW_SECONDS",
        "AI_RATE_LIMIT_WINDOW_SECONDS",
        "AI_RATE_LIMIT_PER_USER",
        "AI_RATE_LIMIT_PER_WORKSPACE",
        "AI_RATE_LIMIT_FIX_PER_USER",
        "AI_DAILY_REQUEST_BUDGET",
        "AI_DAILY_TOKEN_BUDGET",
    }
)
