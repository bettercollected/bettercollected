//! Identifiers derived by hashing: rate-limit counters, option-source ids,
//! counts, advisory-lock keys, idempotency records, deterministic record ids
//! and the hashes of canonical JSON (`ETag`s). Each is a pure function of its
//! input, shared with the Python backend through the database, so a mixed
//! fleet must compute the same value.

use bc_config::secrets::KeyRing;
use serde_json::Value;
use sha1::{Digest as _, Sha1};
use sha2::Sha256;

use crate::prim::{SubKey, derive_all, sha256_hex};
use crate::pyjson;

// ---- rate limiter (services/rate_limiter.py) -----------------------------

pub const RATE_LIMIT_LABEL: &[u8] = b"bettercollected rate-limit counter v1\0";

/// The key of the limiter: the current member of the JWT ring, hashed with the
/// label (counters are windows of seconds or minutes, so only the first member
/// is used).
pub fn rate_limit_key(ring: &KeyRing) -> SubKey {
    SubKey::hashed(ring.members().next().unwrap_or(""), RATE_LIMIT_LABEL)
}

/// `counter_id`: 24 hex characters of the HMAC of `scope \n client \n window`.
pub fn rate_limit_counter_id(key: &SubKey, scope: &str, client: &str, window: i64) -> String {
    key.mac_hex(format!("{scope}\n{client}\n{window}").as_bytes())[..24].to_string()
}

// ---- option sources (services/option_sources/ids.py) ---------------------

pub const OPTION_ID_LABEL: &[u8] = b"bettercollected/option-source-id/v1";
pub const LIST_PREFIX: &str = "li";
pub const ANSWER_PREFIX: &str = "fa";
const ID_BODY: usize = 22;

pub fn option_id_keys(ring: &KeyRing) -> Vec<SubKey> {
    derive_all(ring, OPTION_ID_LABEL)
}

/// `answer_option_id` under one key: `fa` + 22 hex characters of the HMAC of
/// `form_answers \0 workspace \0 form \0 question \0 folded label`.
pub fn answer_option_id(
    key: &SubKey,
    workspace_id: &str,
    form_id: &str,
    question_id: &str,
    folded_label: &str,
) -> String {
    let message = [
        "form_answers",
        workspace_id,
        form_id,
        question_id,
        folded_label,
    ]
    .join("\0");
    format!(
        "{ANSWER_PREFIX}{}",
        &key.mac_hex(message.as_bytes())[..ID_BODY]
    )
}

/// `new_item_id`: `li` + 22 random hex characters.
pub fn new_item_id() -> String {
    format!("{LIST_PREFIX}{}", crate::random::token_hex(ID_BODY / 2))
}

/// `is_source_id`.
pub fn is_source_id(value: &str) -> bool {
    value.len() == 2 + ID_BODY
        && (value.starts_with(LIST_PREFIX) || value.starts_with(ANSWER_PREFIX))
        && value
            .get(2..)
            .unwrap_or("")
            .bytes()
            .all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
}

// ---- hashes without a key ------------------------------------------------

/// The first `n` hex characters of the SHA-256 of `text`.
pub fn sha256_prefix(text: &str, n: usize) -> String {
    let full = sha256_hex(text.as_bytes());
    full.get(..n).unwrap_or(&full).to_string()
}

/// The fingerprint of the set of visible report questions
/// (`ReportPolicy.fingerprint`): the first 16 hex characters of the hash of the
/// sorted keys joined by newlines.
pub fn visible_fingerprint(visible: &[&str]) -> String {
    let mut sorted = visible.to_vec();
    sorted.sort_unstable();
    sha256_prefix(&sorted.join("\n"), 16)
}

/// `captcha_count_id`: 24 hex characters of the hash of the five fields
/// (day, workspace, form, purpose, outcome) joined by newlines.
pub fn captcha_count_id(key: [&str; 5]) -> String {
    sha256_prefix(&key.join("\n"), 24)
}

/// `target_id` of the built-in action migration: 24 hex characters.
pub fn builtin_target_id(kind: &str, form_id: &str, action_id: &str) -> String {
    sha256_prefix(&format!("builtin:{kind}:{form_id}:{action_id}"), 24)
}

/// `idempotency_key` of a custom-domain registration attempt.
pub fn custom_domain_idempotency_key(workspace_id: &str, hostname: &str, attempt: &str) -> String {
    format!(
        "ws-{workspace_id}-{}-{attempt}",
        sha256_prefix(hostname, 32)
    )
}

/// The id of a public-API idempotency record: 24 hex characters of the hash of
/// `key id \n idempotency key`.
pub fn idempotency_record_id(key_id: &str, idempotency_key: &str) -> String {
    sha256_prefix(&format!("{key_id}\n{idempotency_key}"), 24)
}

/// `request_hash`: the fingerprint of a request. A JSON body is compared by
/// value (the canonical form of what `json.loads` reads: integers of any size
/// exact, `-0` is `0`, floats correctly rounded, `NaN` accepted), anything
/// else byte for byte; every part is followed by a NUL. A body that is JSON for
/// Python but that [`pyjson::parse`] declines (UTF-16, nesting beyond 500) is
/// hashed as bytes here.
pub fn request_hash(method: &str, path: &str, body: &[u8], extra: &[&str]) -> String {
    let canonical =
        pyjson::parse(body).map_or_else(|| body.to_vec(), |v| v.canonical().into_bytes());
    let mut hash = Sha256::new();
    let upper = method.to_uppercase();
    let parts: Vec<&[u8]> = [upper.as_bytes(), path.as_bytes(), &canonical]
        .into_iter()
        .chain(extra.iter().map(|e| e.as_bytes()))
        .collect();
    for part in parts {
        sha2::Digest::update(&mut hash, part);
        sha2::Digest::update(&mut hash, [0u8]);
    }
    hex::encode(sha2::Digest::finalize(hash))
}

/// The hex SHA-256 of the canonical JSON of `value`
/// (`json.dumps(value, sort_keys=True, separators=(",", ":"))`), cut to `n`.
/// `value` is a document already parsed by `serde_json` (an integer beyond 64
/// bits is already a float there): for a request body use [`canonical_hash_json`].
pub fn canonical_hash(value: &Value, n: usize) -> String {
    canonical_hash_json(&pyjson::Json::from_value(value), n)
}

/// [`canonical_hash`] of a value read with [`pyjson::parse`].
pub fn canonical_hash_json(value: &pyjson::Json, n: usize) -> String {
    sha256_prefix(&value.canonical(), n)
}

/// `form_etag`: `"<updated ms as lower hex>-<16 hex of the canonical hash>"`,
/// quotes included.
pub fn form_etag(updated_at_ms: u64, document: &Value) -> String {
    format!("\"{updated_at_ms:x}-{}\"", canonical_hash(document, 16))
}

/// `event_key` of a SCIM webhook event (the parsed body of the request):
/// SHA-256 hex of the canonical JSON of
/// `[directory id, event name, data, timestamp ms, index]`.
pub fn scim_event_key(
    directory_id: &str,
    event: &pyjson::Json,
    timestamp_ms: i64,
    index: i64,
) -> String {
    // the canonical text of the list, written from the canonical text of its
    // parts (no copy of the event, which may be nested to the parser's limit)
    let part = |name: &str| {
        event
            .get(name)
            .map_or_else(|| "null".to_string(), pyjson::Json::canonical)
    };
    let text = format!(
        "[{},{},{},{timestamp_ms},{index}]",
        pyjson::quote(directory_id),
        part("event"),
        part("data")
    );
    sha256_hex(text.as_bytes())
}

/// The component id of an Open Formulieren export: `e` + 6 hex characters of
/// the SHA-1 of `seed:key`.
pub fn open_formulieren_component_id(seed: &str, key: &str) -> String {
    format!(
        "e{}",
        &hex::encode(Sha1::digest(format!("{seed}:{key}").as_bytes()))[..6]
    )
}

// ---- advisory locks (repositories/postgres/*.py) -------------------------

/// `_advisory_lock`'s key: the first 8 bytes (big endian, signed) of the SHA-1
/// of the parts joined with NUL. A Rust writer and a Python writer must take
/// the same lock for the same natural key.
pub fn advisory_lock_key(parts: &[&str]) -> i64 {
    let digest = Sha1::digest(parts.join("\0").as_bytes());
    let mut first = [0u8; 8];
    first.copy_from_slice(&digest[..8]);
    i64::from_be_bytes(first)
}

/// `_workspace_lock_key` of the response export (`"response-export|"`) and
/// import (`"response-import|"`) repositories.
pub fn workspace_lock_key(prefix: &str, workspace_id: &str) -> i64 {
    let digest = Sha1::digest(format!("{prefix}{workspace_id}").as_bytes());
    let mut first = [0u8; 8];
    first.copy_from_slice(&digest[..8]);
    i64::from_be_bytes(first)
}
