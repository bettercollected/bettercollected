#!/bin/bash
# Makes sure the root .env (docker compose's substitution file) holds this
# stack's own signing and encryption keys; docker-compose.deployment.yml passes
# them to the services. deploy.sh runs it before anything starts.
#
#   AUTH_JWT_SECRET           signs session tokens (backend, auth, integrations)
#   AUTH_AES_HEX_KEY          a Fernet key, despite the name: OAuth and SSO
#                             state, form-action secrets, SCIM webhook secrets,
#                             Google credentials (also the workers' AES_HEX_KEY)
#   MASTER_ENCRYPTION_KEYSET  the Tink keyset responses are encrypted with
#
# A value already in the root .env is never changed. A value set in
# .env.deployment (where these used to live) is copied over, unless it is one
# that was published in the repository. Anything else is generated.
#
# Usage: deploy/generate-secrets.sh [ROOT_ENV] [DEPLOYMENT_ENV]
# BC_EXISTING_STACK=true says the stack already holds data (deploy.sh checks):
# then a missing MASTER_ENCRYPTION_KEYSET is an error, not generated, because a
# new keyset could not read the responses stored so far.

set -euo pipefail
umask 077

root_env="${1:-.env}"
deployment_env="${2:-.env.deployment}"
existing_stack="${BC_EXISTING_STACK:-false}"

# SHA-256 of values published for AUTH_JWT_SECRET / AUTH_AES_HEX_KEY, never the
# values; the same list as common/common/configs/shipped_secrets.py.
shipped_sha256="
a75934b93de0f24eb3da8b1f4234d7c3dfcf8f057377739a7378383898555de3
af61f0e17db65ce007dccccd9165d3467e9c97c3d12e4c9507a9a06ec7aa1103
dfad509a1373435ed0c21fd96e686e3a6879d30dae9796ac1eec38b6916497be
4f4c538d1c81f4b9083fc33240e62f4101f1d21434b4f698f0d03f77a5d89207
5a90a68596fcebfd2676d9313557584bd68b143dd234750c419ece1b8f82fe5a
33d902e58f189bbb7266454cdbd9741bb3bd956a300c4a04ef0b24cd221a2da3
c47af94f4a9ae7811b6d01bf1abb251f927ec915c8d78bbe07b56d513295058a
0cf506f170c8c321831425c7a7cc8dc745a0104493b7e98d1ed653bb1e5f913b
"

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$1" | sha256sum | cut -d' ' -f1
  else
    printf '%s' "$1" | shasum -a 256 | cut -d' ' -f1
  fi
}

is_shipped() {
  local digest
  digest=$(sha256 "$1")
  [[ "$shipped_sha256" == *"$digest"* ]]
}

# The last assignment of $2 in file $1, trimmed and unquoted ("" if none).
read_var() {
  local file=$1 var=$2 value
  [ -f "$file" ] || return 0
  value=$(grep -E "^${var}=" "$file" | tail -n 1 || true)
  value=${value#*=}
  value=$(printf '%s' "$value" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')
  if [[ ${#value} -ge 2 && ( "$value" == \'*\' || "$value" == \"*\" ) ]]; then
    value=${value:1:${#value}-2}
  fi
  printf '%s' "$value"
}

# Writes VAR=VALUE to the root .env, dropping an empty assignment of VAR first.
set_var() {
  local var=$1 value=$2 tmp
  if [ -f "$root_env" ] && grep -qE "^${var}=" "$root_env"; then
    tmp=$(mktemp "${root_env}.XXXXXX")
    grep -vE "^${var}=" "$root_env" > "$tmp" || true
    mv "$tmp" "$root_env"
  fi
  printf '%s=%s\n' "$var" "$value" >> "$root_env"
}

generate() {
  local key_id key_value
  case "$1" in
    jwt) openssl rand -hex 32 ;;
    # Fernet: 32 random bytes, url-safe base64
    fernet) openssl rand 32 | base64 | tr -d '\n' | tr '+/' '-_' ;;
    # Tink AEAD keyset with one AES-256-GCM key: JSON, base64-encoded. The
    # key's value is the serialized AesGcmKey proto (field 3, 32 bytes).
    keyset)
      key_id=$(( 16#$(openssl rand -hex 4) & 0x7fffffff ))
      [ "$key_id" -gt 0 ] || key_id=1
      key_value=$({ printf '\032\040'; openssl rand 32; } | base64 | tr -d '\n')
      printf '{"primaryKeyId":%d,"key":[{"keyData":{"typeUrl":"type.googleapis.com/google.crypto.tink.AesGcmKey","value":"%s","keyMaterialType":"SYMMETRIC"},"status":"ENABLED","keyId":%d,"outputPrefixType":"TINK"}]}' \
        "$key_id" "$key_value" "$key_id" | base64 | tr -d '\n'
      ;;
  esac
}

failed=false

ensure_secret() {
  local var=$1 kind=$2 current
  current=$(read_var "$root_env" "$var")
  if [ -n "$current" ]; then
    if [ "$kind" != keyset ] && is_shipped "$current"; then
      echo "${var} in ${root_env} is a value that was published in the bettercollected repository. Replace it with your own (or delete the line and re-run to generate one)." >&2
      failed=true
    fi
    return 0
  fi

  current=$(read_var "$deployment_env" "$var")
  if [ -n "$current" ]; then
    if [ "$kind" = keyset ] || ! is_shipped "$current"; then
      set_var "$var" "$current"
      echo "Copied ${var} from ${deployment_env} into ${root_env}; it is read from there now."
      return 0
    fi
    echo "Not using ${var} from ${deployment_env}: it is a value that was published in the bettercollected repository. Remove it there." >&2
  fi

  if [ "$kind" = keyset ] && [ "$existing_stack" = true ]; then
    echo "MASTER_ENCRYPTION_KEYSET is not set, and this stack already holds data. Responses are encrypted with it, so a new keyset could not read them. Add the keyset this stack has used so far to ${root_env} as MASTER_ENCRYPTION_KEYSET=... (until this release it came from .env.deployment, see CHANGELOG.md) and re-run." >&2
    failed=true
    return 0
  fi

  set_var "$var" "$(generate "$kind")"
  echo "Generated a new ${var} in ${root_env}."
  if [ "$existing_stack" = true ]; then
    case "$kind" in
      jwt) echo "  Everyone is signed out once the services restart with it." ;;
      fernet) echo "  Data encrypted with the old key can no longer be read: reconnect Google Forms and Google Sheets, re-enter form-action secrets and regenerate SCIM webhook secrets." ;;
    esac
  fi
}

ensure_secret AUTH_JWT_SECRET jwt
ensure_secret AUTH_AES_HEX_KEY fernet
ensure_secret MASTER_ENCRYPTION_KEYSET keyset

if [ "$failed" = true ]; then
  exit 1
fi
