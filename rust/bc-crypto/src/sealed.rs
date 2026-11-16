//! Values the backend seals with the Fernet ring inside a small JSON envelope
//! that names what they belong to, so a ciphertext copied to another row,
//! workspace or purpose is refused: a registration service's secret
//! (`registration/secrets.py`), a webhook address (`webhooks/sealing.py`) and
//! a TOTP factor's shared secret (`mfa/sealing.py`). The other sealed values
//! (OAuth state, deletion and revocation requests, credentials) are plain JSON
//! in a token: [`seal_json`] and [`open_json`].

use serde_json::{Value, json};

use crate::CryptoError;
use crate::fernet::FernetRing;

const VERSION: i64 = 1;
const PURPOSE_WEBHOOK_URL: &str = "webhook_url";
const PURPOSE_TOTP_SECRET: &str = "totp_secret";

/// `crypto.encrypt(json.dumps(value))`.
pub fn seal_json(ring: &FernetRing, value: &Value) -> String {
    ring.seal(value.to_string().as_bytes())
}

/// `json.loads(crypto.decrypt(token, ttl))`.
pub fn open_json(ring: &FernetRing, token: &str, ttl: Option<u64>) -> Result<Value, CryptoError> {
    serde_json::from_str(&ring.open_str(token, ttl)?).map_err(|_| CryptoError::InvalidToken)
}

fn text<'a>(envelope: &'a Value, name: &str) -> Option<&'a str> {
    envelope.get(name).and_then(Value::as_str)
}

fn envelope_ok(envelope: &Value, expected: &[(&str, &str)]) -> bool {
    envelope.is_object()
        && envelope.get("v").and_then(Value::as_i64) == Some(VERSION)
        && expected.iter().all(|(k, v)| text(envelope, k) == Some(*v))
}

/// `registration.secrets.seal`.
pub fn seal_registration_secret(
    ring: &FernetRing,
    workspace_id: &str,
    service_id: &str,
    secret: &str,
) -> String {
    seal_json(
        ring,
        &json!({"v": VERSION, "workspace_id": workspace_id, "service_id": service_id, "secret": secret}),
    )
}

/// `registration.secrets.unseal`: `None` for an empty value, an error for one
/// that is not ours for this service.
pub fn unseal_registration_secret(
    ring: &FernetRing,
    workspace_id: &str,
    service_id: &str,
    sealed: Option<&str>,
) -> Result<Option<String>, CryptoError> {
    let Some(sealed) = sealed.filter(|s| !s.is_empty()) else {
        return Ok(None);
    };
    let envelope = open_json(ring, sealed, None).map_err(|_| CryptoError::Unreadable)?;
    if !envelope_ok(
        &envelope,
        &[("workspace_id", workspace_id), ("service_id", service_id)],
    ) {
        return Err(CryptoError::Unreadable);
    }
    text(&envelope, "secret")
        .map(|s| Some(s.to_string()))
        .ok_or(CryptoError::Unreadable)
}

/// `webhooks.sealing.seal_url`.
pub fn seal_webhook_url(
    ring: &FernetRing,
    workspace_id: &str,
    webhook_id: &str,
    url: &str,
) -> String {
    seal_json(
        ring,
        &json!({"v": VERSION, "purpose": PURPOSE_WEBHOOK_URL, "workspace_id": workspace_id,
                "webhook_id": webhook_id, "url": url}),
    )
}

/// `webhooks.sealing.unseal_url`: an empty or foreign value is an error.
pub fn unseal_webhook_url(
    ring: &FernetRing,
    workspace_id: &str,
    webhook_id: &str,
    sealed: Option<&str>,
) -> Result<String, CryptoError> {
    let envelope =
        open_json(ring, sealed.unwrap_or(""), None).map_err(|_| CryptoError::Unreadable)?;
    if !envelope_ok(
        &envelope,
        &[
            ("purpose", PURPOSE_WEBHOOK_URL),
            ("workspace_id", workspace_id),
            ("webhook_id", webhook_id),
        ],
    ) {
        return Err(CryptoError::Unreadable);
    }
    text(&envelope, "url")
        .filter(|u| !u.is_empty())
        .map(str::to_string)
        .ok_or(CryptoError::Unreadable)
}

/// `mfa.sealing.seal_secret`.
pub fn seal_totp_secret(ring: &FernetRing, user_id: &str, factor_id: &str, secret: &str) -> String {
    seal_json(
        ring,
        &json!({"v": VERSION, "purpose": PURPOSE_TOTP_SECRET, "user_id": user_id,
                "factor_id": factor_id, "secret": secret}),
    )
}

/// `mfa.sealing.unseal_secret`.
pub fn unseal_totp_secret(
    ring: &FernetRing,
    user_id: &str,
    factor_id: &str,
    sealed: Option<&str>,
) -> Result<String, CryptoError> {
    let envelope =
        open_json(ring, sealed.unwrap_or(""), None).map_err(|_| CryptoError::Unreadable)?;
    if !envelope_ok(
        &envelope,
        &[
            ("purpose", PURPOSE_TOTP_SECRET),
            ("user_id", user_id),
            ("factor_id", factor_id),
        ],
    ) {
        return Err(CryptoError::Unreadable);
    }
    text(&envelope, "secret")
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .ok_or(CryptoError::Unreadable)
}
