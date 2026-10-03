#!/usr/bin/env bash
# Dev-only setup for the enterprise SSO spike (docs/sso-spike.md).
#
#   scripts/sso-dev-setup.sh [--seed-workspace] [--domain example.com] [--workspace <id>]
#
# 1. Generates throwaway secrets and the mock IdP's signing key pair in
#    .sso-dev/ (gitignored, never commit it). Re-runs reuse them.
# 2. Creates the `polis` database in app-postgres (docker-compose.local.yml
#    must be up) if it doesn't exist. Nothing else in Postgres is touched.
# 3. Optionally seeds a demo organisation workspace in the local Mongo
#    (--seed-workspace; idempotent, fixed id below).
# 4. Starts Polis + mock SAML (docker-compose.sso.yml) and registers the
#    SAML connection (tenant = workspace id, product = bettercollected)
#    through Polis's admin API from mock-saml's metadata. Idempotent.
# 5. Prints the SSO_* settings for auth/.env.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEV="$ROOT/.sso-dev"
POLIS=http://localhost:5225
MOCK=http://localhost:4000
PRODUCT=bettercollected
DOMAIN=example.com
DEMO_WORKSPACE_ID=65e5501d0000000000000001
DEMO_OWNER_ID=65e5501d0000000000000002
WORKSPACE_ID=""
SEED=0
REDIRECT_URI=http://localhost:8000/api/v1/auth/sso/callback
PG_CONTAINER=${PG_CONTAINER:-bettercollected-app-postgres-1}
MONGO_CONTAINER=${MONGO_CONTAINER:-bettercollected-mongodb-1}

while [ $# -gt 0 ]; do
  case "$1" in
    --seed-workspace) SEED=1 ;;
    --domain) DOMAIN="$2"; shift ;;
    --workspace) WORKSPACE_ID="$2"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
if [ "$SEED" = 1 ] && [ -z "$WORKSPACE_ID" ]; then WORKSPACE_ID=$DEMO_WORKSPACE_ID; fi
if [ -z "$WORKSPACE_ID" ]; then
  echo "pass --workspace <workspace id> or --seed-workspace" >&2; exit 2
fi

umask 077
mkdir -p "$DEV"

# -- 1. secrets + mock IdP key pair (throwaway, local only) -------------------
if [ ! -f "$DEV/mock-saml.key" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 365 \
    -subj "/CN=mock-saml.bettercollected.local" \
    -keyout "$DEV/mock-saml.key" -out "$DEV/mock-saml.crt" 2>/dev/null
fi
cat > "$DEV/mock-saml.env" <<EOF
PRIVATE_KEY=$(base64 -w0 "$DEV/mock-saml.key")
PUBLIC_KEY=$(base64 -w0 "$DEV/mock-saml.crt")
EOF
if [ ! -f "$DEV/polis.env" ]; then
  cat > "$DEV/polis.env" <<EOF
JACKSON_API_KEYS=$(openssl rand -hex 24)
DB_URL=postgres://bettercollected:bettercollected@app-postgres:5432/polis
DB_ENCRYPTION_KEY=$(openssl rand -hex 16)
NEXTAUTH_SECRET=$(openssl rand -hex 32)
NEXTAUTH_ADMIN_CREDENTIALS=admin@example.com:$(openssl rand -hex 12)
CLIENT_SECRET_VERIFIER=$(openssl rand -hex 24)
EOF
fi
# shellcheck disable=SC1091
set -a; . "$DEV/polis.env"; set +a
API_KEY=${JACKSON_API_KEYS%%,*}

# -- 2. polis database ---------------------------------------------------------
if ! docker exec "$PG_CONTAINER" psql -U bettercollected -d postgres -Atc \
    "select 1 from pg_database where datname = 'polis'" | grep -q 1; then
  docker exec "$PG_CONTAINER" psql -U bettercollected -d postgres -c "create database polis" >/dev/null
  echo "created database polis"
fi

# -- 3. demo workspace (optional) ---------------------------------------------
if [ "$SEED" = 1 ]; then
  MONGO_URI=$(grep -E '^MONGO_URI=' "$ROOT/backend/.env" | cut -d= -f2-)
  BACKEND_DB=$(grep -E '^MONGO_DB=' "$ROOT/backend/.env" | cut -d= -f2-)
  AUTH_DB=$(grep -E '^MONGO_DB=' "$ROOT/auth/.env" | cut -d= -f2-)
  docker exec "$MONGO_CONTAINER" mongosh "$MONGO_URI/?authSource=admin" --quiet --eval "
    const now = new Date().toISOString();
    const owner = ObjectId('$DEMO_OWNER_ID'), ws = ObjectId('$WORKSPACE_ID');
    db.getSiblingDB('$AUTH_DB').users.updateOne({_id: owner}, {\$setOnInsert: {
      email: 'owner@$DOMAIN', roles: ['FORM_RESPONDER', 'FORM_CREATOR'], plan: 'FREE',
      first_name: 'Org', last_name: 'Owner', created_at: now, updated_at: now}}, {upsert: true});
    const b = db.getSiblingDB('$BACKEND_DB');
    b.workspaces.updateOne({_id: ws}, {\$setOnInsert: {
      title: 'Example Corp (SSO spike)', workspace_name: 'example-corp-sso', description: '',
      owner_id: '$DEMO_OWNER_ID', default: false, disabled: false, profile_image: '', banner_image: '',
      ai_enabled: false, created_at: now, updated_at: now}}, {upsert: true});
    b.workspace_users.updateOne({workspace_id: ws, user_id: owner}, {\$setOnInsert: {
      roles: ['ADMIN'], disabled: false, created_at: now, updated_at: now}}, {upsert: true});
    print('demo workspace example-corp-sso = ' + ws.toHexString());
  "
fi

# -- 4. Polis + mock IdP, SAML connection -------------------------------------
docker compose -f "$ROOT/docker-compose.sso.yml" --project-name bettercollected-sso up -d
for url in "$POLIS/api/health" "$MOCK/api/health"; do
  for _ in $(seq 1 60); do curl -fsS "$url" >/dev/null 2>&1 && break; sleep 2; done
  curl -fsS "$url" >/dev/null || { echo "not healthy: $url" >&2; exit 1; }
done

existing=$(curl -fsS -H "Authorization: Api-Key $API_KEY" \
  "$POLIS/api/v1/sso?tenant=$WORKSPACE_ID&product=$PRODUCT")
if [ "$(echo "$existing" | jq 'length')" = "0" ]; then
  metadata=$(curl -fsS "$MOCK/api/saml/metadata")
  jq -n --arg md "$metadata" --arg t "$WORKSPACE_ID" --arg p "$PRODUCT" --arg r "$REDIRECT_URI" '{
      name: "Mock SAML (dev)", description: "SSO spike", tenant: $t, product: $p,
      rawMetadata: $md, defaultRedirectUrl: $r, redirectUrl: ([$r] | tojson)}' |
    curl -fsS -X POST -H "Authorization: Api-Key $API_KEY" -H "Content-Type: application/json" \
      --data @- "$POLIS/api/v1/sso" | jq '{clientID, tenant, product, redirectUrl}'
  echo "registered the SAML connection"
else
  echo "SAML connection already registered for tenant $WORKSPACE_ID"
fi

cat <<EOF

Polis admin UI: $POLIS (credentials in .sso-dev/polis.env, NEXTAUTH_ADMIN_CREDENTIALS)
Settings for auth (env or auth/.env):
  SSO_ENABLED=true
  SSO_POLIS_URL=$POLIS
  SSO_REDIRECT_URI=$REDIRECT_URI
  SSO_POLIS_CLIENT_SECRET=<CLIENT_SECRET_VERIFIER from .sso-dev/polis.env>
  SSO_DOMAIN_TENANTS=$DOMAIN:$WORKSPACE_ID
Webapp: NEXT_PUBLIC_ENABLE_SSO=true
EOF
