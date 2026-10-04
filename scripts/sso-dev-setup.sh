#!/usr/bin/env bash
# Local development of single sign-on (docs/sso.md).
#
#   scripts/sso-dev-setup.sh [--seed-workspace] [--domain example.com] [--workspace <id>]
#
# 1. Generates throwaway secrets and the mock IdP's signing key pair in
#    .sso-dev/ (gitignored, never commit it). Re-runs reuse them.
# 2. Creates the `polis` database in app-postgres (docker-compose.local.yml
#    must be up) if it doesn't exist. Nothing else in Postgres is touched.
# 3. Optionally (--seed-workspace) seeds a demo workspace with its owner in the
#    local Mongo and marks --domain (default example.com) as *verified* for it,
#    or (--workspace <id>) marks the domain verified for an existing workspace.
#    This is a local-only shortcut: the mock IdP only issues @example.com /
#    @example.org addresses, which the domain verification refuses to claim
#    (documentation domains), and there is no DNS to publish a TXT record in.
#    Idempotent; it never touches a domain verified by another workspace.
# 4. Starts Polis + the mock SAML IdP (docker-compose.sso.yml).
# 5. Prints the SSO_* settings for backend/.env and auth/.env.
#
# Connections are NOT created here: add one in the app (workspace settings ->
# Single sign-on -> Add connection -> SAML -> paste the XML from
# http://localhost:4000/api/saml/metadata; a localhost metadata URL is refused
# on purpose), test it, enable it.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEV="$ROOT/.sso-dev"
POLIS=http://localhost:5225
MOCK=http://localhost:4000
DOMAIN=example.com
DEMO_WORKSPACE_ID=65e5501d0000000000000001
DEMO_OWNER_ID=65e5501d0000000000000002
WORKSPACE_ID=""
SEED=0
BACKEND_URL=${BACKEND_URL:-http://localhost:8000}
REDIRECT_URI="$BACKEND_URL/api/v1/auth/sso/callback"
PG_CONTAINER=${PG_CONTAINER:-bettercollected-app-postgres-1}
# Polis's database in app-postgres (for a new .sso-dev/ only). Its rows are
# encrypted with the DB_ENCRYPTION_KEY in .sso-dev/polis.env, so new secrets
# need a new (or emptied) database.
POLIS_DB=${POLIS_DB:-polis}
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
DB_URL=postgres://bettercollected:bettercollected@app-postgres:5432/$POLIS_DB
DB_ENCRYPTION_KEY=$(openssl rand -hex 16)
NEXTAUTH_SECRET=$(openssl rand -hex 32)
NEXTAUTH_ADMIN_CREDENTIALS=admin@example.com:$(openssl rand -hex 12)
CLIENT_SECRET_VERIFIER=$(openssl rand -hex 24)
EOF
fi

# -- 2. polis database ---------------------------------------------------------
POLIS_DB=$(grep -E '^DB_URL=' "$DEV/polis.env" | sed 's#.*/##')
if ! docker exec "$PG_CONTAINER" psql -U bettercollected -d postgres -Atc \
    "select 1 from pg_database where datname = '$POLIS_DB'" | grep -q 1; then
  docker exec "$PG_CONTAINER" psql -U bettercollected -d postgres -c "create database \"$POLIS_DB\"" >/dev/null
  echo "created database $POLIS_DB"
fi

# -- 3. demo workspace and a verified domain (optional, local only) -----------
if [ -n "$WORKSPACE_ID" ]; then
  MONGO_URI=${MONGO_URI:-$(grep -E "^MONGO_URI=" "$ROOT/backend/.env" | cut -d= -f2-)}
  BACKEND_DB=${BACKEND_DB:-$(grep -E '^MONGO_DB=' "$ROOT/backend/.env" | cut -d= -f2-)}
  AUTH_DB=${AUTH_DB:-$(grep -E '^MONGO_DB=' "$ROOT/auth/.env" | cut -d= -f2-)}
  docker exec "$MONGO_CONTAINER" mongosh "$MONGO_URI/?authSource=admin" --quiet --eval "
    const now = new Date();
    const ws = ObjectId('$WORKSPACE_ID');
    const b = db.getSiblingDB('$BACKEND_DB');
    if ($SEED === 1) {
      const owner = ObjectId('$DEMO_OWNER_ID');
      db.getSiblingDB('$AUTH_DB').users.updateOne({_id: owner}, {\$setOnInsert: {
        email: 'owner@$DOMAIN', roles: ['FORM_RESPONDER', 'FORM_CREATOR'], plan: 'FREE',
        first_name: 'Org', last_name: 'Owner', created_at: now.toISOString(), updated_at: now.toISOString()}}, {upsert: true});
      b.workspaces.updateOne({_id: ws}, {\$setOnInsert: {
        title: 'Example Corp (SSO dev)', workspace_name: 'example-corp-sso', description: '',
        owner_id: '$DEMO_OWNER_ID', default: false, disabled: false, profile_image: '', banner_image: '',
        ai_enabled: false, created_at: now.toISOString(), updated_at: now.toISOString()}}, {upsert: true});
      b.workspace_users.updateOne({workspace_id: ws, user_id: owner}, {\$setOnInsert: {
        roles: ['ADMIN'], disabled: false, created_at: now, updated_at: now}}, {upsert: true});
    }
    const held = b.workspace_domains.findOne({verified_domain: '$DOMAIN'});
    if (held && !held.workspace_id.equals(ws)) {
      print('$DOMAIN is verified by another workspace; left alone');
    } else {
      b.workspace_domains.updateOne({workspace_id: ws, domain: '$DOMAIN'}, {
        \$set: {status: 'verified', verified_domain: '$DOMAIN', verified_at: now,
               last_checked_at: now, last_check_error: null, failed_checks: 0,
               verification_lost_at: null, updated_at: now},
        \$setOnInsert: {verification_token: 'local-dev-' + ws.toHexString(), method: 'dns_txt',
                        created_by: 'sso-dev-setup', created_at: now}}, {upsert: true});
      print('$DOMAIN marked verified for workspace ' + ws.toHexString() + ' (local dev only)');
    }
  "
fi

# -- 4. Polis + mock IdP --------------------------------------------------------
docker compose -f "$ROOT/docker-compose.sso.yml" --project-name bettercollected-sso up -d
for url in "$POLIS/api/health" "$MOCK/api/health"; do
  for _ in $(seq 1 60); do curl -fsS "$url" >/dev/null 2>&1 && break; sleep 2; done
  curl -fsS "$url" >/dev/null || { echo "not healthy: $url" >&2; exit 1; }
done

cat <<EOF

Polis: $POLIS   Mock IdP: $MOCK (metadata: $MOCK/api/saml/metadata)
Settings for backend/.env (the API key is JACKSON_API_KEYS in .sso-dev/polis.env):
  SSO_ENABLED=true
  SSO_POLIS_URL=$POLIS
  SSO_POLIS_API_KEY=<JACKSON_API_KEYS from .sso-dev/polis.env>
  SSO_REDIRECT_URI=$REDIRECT_URI
  SSO_SAML_AUDIENCE=https://saml.bettercollected.local
Settings for auth/.env:
  SSO_ENABLED=true
  SSO_POLIS_URL=$POLIS
  SSO_REDIRECT_URI=$REDIRECT_URI
Webapp: NEXT_PUBLIC_ENABLE_SSO=true
Teardown: docker compose -f docker-compose.sso.yml -p bettercollected-sso down
(and drop the $POLIS_DB database to wipe Polis's data)
EOF
