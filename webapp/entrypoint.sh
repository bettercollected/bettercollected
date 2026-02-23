#!/bin/sh

# ────────────────────────────────────────────────────────────────
# Elastic APM configuration check & setup for Next.js (elastic-apm-node 4.x)
# ────────────────────────────────────────────────────────────────

MISSING=""

if [ -z "$ELASTIC_APM_SERVER_URL" ]; then
    MISSING="$MISSING ELASTIC_APM_SERVER_URL"
fi

if [ -z "$ELASTIC_APM_SERVICE_NAME" ]; then
    MISSING="$MISSING ELASTIC_APM_SERVICE_NAME"
fi

# API key is preferred in 4.x (secretToken is legacy/deprecated in many setups)
if [ -z "$ELASTIC_APM_API_KEY" ] && [ -z "$ELASTIC_APM_SECRET_TOKEN" ]; then
    MISSING="$MISSING ELASTIC_APM_API_KEY (or ELASTIC_APM_SECRET_TOKEN)"
fi

if [ -n "$MISSING" ]; then
    echo "[WARN] Elastic APM NOT fully configured. Missing:${MISSING}" >&2
    # You can decide to continue anyway or exit 1 — usually continue
else
    # ─── Modern way: just --require the agent (no start-next.js anymore) ───
    # This starts the agent **very early** — best for auto-instrumentation
    export NODE_OPTIONS="--require elastic-apm-node ${NODE_OPTIONS:-}"
    ELASTIC_APM_ENVIRONMENT=${ELASTIC_APM_ENVIRONMENT:-production}

    echo "Elastic APM configured (v4.x) → server: ${ELASTIC_APM_SERVER_URL}"
fi

# Start Next.js
exec ./node_modules/.bin/next start