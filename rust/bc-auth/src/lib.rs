//! Verification of the session cookies the Python backend issues.
//!
//! Same rules as `common/services/jwt_service.py` `decode_with_ring` plus
//! `backend/app/services/session_service.py` `user_from_access_token`:
//! HS256 only (the algorithm is pinned, whatever the header says), every
//! member of the `AUTH_JWT_SECRET` ring verifies, `exp`/`nbf`/`iat` are
//! checked when present with no leeway, `typ` must be "access" and `sid`
//! must be set. The access token is trusted as it is, with no database read.
//!
//! Not here yet: the session refresh (an expired access token with a
//! `RefreshToken` cookie), which reads the session and calls the auth
//! service. A route that meets that case hands the request to the Python
//! backend.

use bc_config::KeyRing;
use jsonwebtoken::{Algorithm, DecodingKey, Validation, decode};
use serde_json::{Map, Value};
use std::time::{SystemTime, UNIX_EPOCH};

pub const ACCESS_COOKIE: &str = "Authorization";
pub const REFRESH_COOKIE: &str = "RefreshToken";

/// What the permission check needs of `common.models.user.User`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct User {
    pub id: String,
    pub sub: String,
    pub session_scope: Option<String>,
    pub scope_workspace_id: Option<String>,
    pub auth_method: Option<String>,
    pub sso_workspace_id: Option<String>,
    pub mfa: bool,
}

fn now_seconds() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0.0, |d| d.as_secs_f64())
}

#[cfg(test)]
fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_secs())
}

/// PyJWT's `int(value)` for a claim: an integer, a float (truncated toward
/// zero), a boolean (`True` is 1) or a string `int()` reads (surrounding white
/// space, an optional sign, ASCII digits with single underscores between
/// them). `None` where PyJWT raises: null, arrays, objects, `"1.5"`, `"abc"`,
/// an infinite float. (Digits of other scripts, which `int()` also reads, are
/// refused here: a token then fails closed.) The value is returned as `f64`:
/// it is only ever compared with the current time.
fn py_int(value: &Value) -> Option<f64> {
    match value {
        Value::Bool(b) => Some(f64::from(u8::from(*b))),
        Value::Number(n) => {
            let f = n.as_f64()?;
            f.is_finite().then(|| f.trunc())
        }
        Value::String(s) => {
            let t = s.trim();
            let digits = t.strip_prefix(['+', '-']).unwrap_or(t);
            let well_formed = !digits.is_empty()
                && digits.bytes().all(|b| b.is_ascii_digit() || b == b'_')
                && !digits.starts_with('_')
                && !digits.ends_with('_')
                && !digits.contains("__");
            if !well_formed {
                return None;
            }
            let number: String = digits.chars().filter(|c| *c != '_').collect();
            let magnitude = number.parse::<f64>().ok()?;
            Some(if t.starts_with('-') {
                -magnitude
            } else {
                magnitude
            })
        }
        _ => None,
    }
}

/// `PyJWT._validate_claims` with no leeway: `iat` and `nbf` must read as
/// integers and not lie in the future, `exp` must read as an integer and lie in
/// the future (`exp <= now` is expired). A claim that is absent is not checked.
fn time_claims_hold(claims: &Map<String, Value>, now: f64) -> bool {
    if let Some(iat) = claims.get("iat")
        && !py_int(iat).is_some_and(|v| v <= now)
    {
        return false;
    }
    if let Some(nbf) = claims.get("nbf")
        && !py_int(nbf).is_some_and(|v| v <= now)
    {
        return false;
    }
    if let Some(exp) = claims.get("exp")
        && !py_int(exp).is_some_and(|v| v > now)
    {
        return false;
    }
    true
}

/// The claims of `token` when some member of the ring verifies it and the
/// time claims hold; `None` otherwise (Python's `decode_token` returns None
/// on any `PyJWTError`).
pub fn decode_with_ring(token: &str, ring: &KeyRing) -> Option<Map<String, Value>> {
    let mut validation = Validation::new(Algorithm::HS256);
    validation.leeway = 0;
    // The signature and the algorithm are checked by jsonwebtoken; the time
    // claims are checked below with PyJWT's own coercion. jsonwebtoken silently
    // skips an `exp` or `nbf` it cannot read as an unsigned integer, which would
    // let a validly signed token with a float or string `exp` live forever.
    validation.validate_exp = false;
    validation.validate_nbf = false;
    validation.validate_aud = false;
    // PyJWT does not require `exp`; it checks it when present
    validation.required_spec_claims.clear();
    for member in ring.members() {
        let key = DecodingKey::from_secret(member.as_bytes());
        match decode::<Value>(token, &key, &validation) {
            Ok(data) => {
                let Value::Object(claims) = data.claims else {
                    return None;
                };
                // PyJWT: a token that carries `aud` is refused when the
                // caller names no audience
                if claims.contains_key("aud") {
                    return None;
                }
                if !time_claims_hold(&claims, now_seconds()) {
                    return None;
                }
                return Some(claims);
            }
            Err(error) => {
                use jsonwebtoken::errors::ErrorKind::InvalidSignature;
                if matches!(error.kind(), InvalidSignature) {
                    continue; // try the previous member
                }
                // a member verified the signature but a claim failed, or the
                // token is not decodable at all: no other member changes that
                return None;
            }
        }
    }
    None
}

// outer `None`: a value pydantic refuses; inner `None`: a null (absent)
#[allow(clippy::option_option)]
fn text(value: &Value) -> Option<Option<String>> {
    match value {
        Value::Null => Some(None),
        Value::String(s) => Some(Some(s.clone())),
        _ => None,
    }
}

/// pydantic's lax bool for `Optional[bool]`.
#[allow(clippy::option_option)]
fn lax_bool(value: &Value) -> Option<Option<bool>> {
    match value {
        Value::Null => Some(None),
        Value::Bool(b) => Some(Some(*b)),
        Value::Number(n) => match n.as_i64() {
            Some(0) => Some(Some(false)),
            Some(1) => Some(Some(true)),
            _ => None,
        },
        Value::String(s) => bc_config::source::parse_bool(s).map(Some),
        _ => None,
    }
}

/// `user_from_access_token`: the user of a live access token of a session.
pub fn user_from_access_token(token: Option<&str>, ring: &KeyRing) -> Option<User> {
    let token = token.filter(|t| !t.is_empty())?;
    let claims = decode_with_ring(token, ring)?;
    if claims.get("typ").and_then(Value::as_str) != Some("access") {
        return None;
    }
    // `not claims.get("sid")`: absent, null, "" (and 0/false/[]/{}) all count as none
    let sid_set = match claims.get("sid") {
        None | Some(Value::Null | Value::Bool(false)) => false,
        Some(Value::String(s)) => !s.is_empty(),
        Some(Value::Number(n)) => n.as_f64().is_none_or(|f| f != 0.0),
        Some(Value::Array(a)) => !a.is_empty(),
        Some(Value::Object(o)) => !o.is_empty(),
        Some(Value::Bool(true)) => true,
    };
    if !sid_set {
        return None;
    }
    build_user(&claims)
}

/// `User(**claims)` of common/models/user.py: a claim of the wrong type makes
/// pydantic raise, which Python reads as "not a live token".
fn build_user(claims: &Map<String, Value>) -> Option<User> {
    let id = claims.get("id")?.as_str()?.to_string();
    let sub = claims.get("sub")?.as_str()?.to_string();
    if let Some(plan) = claims.get("plan") {
        match plan {
            Value::Null => {}
            Value::String(p) if p == "FREE" || p == "PRO" => {}
            _ => return None,
        }
    }
    if let Some(roles) = claims.get("roles") {
        match roles {
            Value::Null => {}
            Value::Array(items) if items.iter().all(Value::is_string) => {}
            _ => return None,
        }
    }
    let optional_text = |key: &str| -> Option<Option<String>> {
        match claims.get(key) {
            None => Some(None),
            Some(v) => text(v),
        }
    };
    let optional_bool = |key: &str| -> Option<Option<bool>> {
        match claims.get(key) {
            None => Some(None),
            Some(v) => lax_bool(v),
        }
    };
    optional_bool("email_verified")?;
    optional_text("sid")?;
    let mfa = optional_bool("mfa")?;
    Some(User {
        id,
        sub,
        session_scope: optional_text("session_scope")?,
        scope_workspace_id: optional_text("scope_workspace_id")?,
        auth_method: optional_text("auth_method")?,
        sso_workspace_id: optional_text("sso_workspace_id")?,
        mfa: mfa.unwrap_or(false),
    })
}

fn unquote(value: &str) -> String {
    // http.cookies._unquote: a quoted string loses its quotes and its escapes
    if value.len() < 2 || !value.starts_with('"') || !value.ends_with('"') {
        return value.to_string();
    }
    let inner = &value[1..value.len() - 1];
    let mut out = String::new();
    let mut chars = inner.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\\' {
            match chars.peek().copied() {
                Some(d) if d.is_ascii_digit() => {
                    let digits: String = chars.by_ref().take(3).collect();
                    if digits.len() == 3
                        && digits.chars().all(|c| ('0'..='7').contains(&c))
                        && let Ok(v) = u8::from_str_radix(&digits, 8)
                    {
                        out.push(char::from(v));
                        continue;
                    }
                    out.push('\\');
                    out.push_str(&digits);
                }
                Some(d) => {
                    out.push(d);
                    chars.next();
                }
                None => out.push('\\'),
            }
        } else {
            out.push(c);
        }
    }
    out
}

/// Starlette's `cookie_parser`: `key=value` chunks split on `;`, trimmed,
/// later duplicates win, quoted values unquoted.
pub fn parse_cookies(header: &str) -> std::collections::HashMap<String, String> {
    let mut map = std::collections::HashMap::new();
    for chunk in header.split(';') {
        let (key, value) = match chunk.split_once('=') {
            Some((k, v)) => (k.trim(), v.trim()),
            None => ("", chunk.trim()),
        };
        map.insert(key.to_string(), unquote(value));
    }
    map
}

#[cfg(test)]
mod tests {
    #![allow(clippy::cast_precision_loss)]
    use super::*;
    use jsonwebtoken::{EncodingKey, Header, encode};
    use serde_json::json;

    fn members() -> Vec<String> {
        vec!["k".repeat(40), "o".repeat(40)]
    }

    fn ring() -> KeyRing {
        KeyRing::from_members(members())
    }

    #[allow(clippy::needless_pass_by_value)]
    fn sign(claims: Value, secret: &str, alg: Algorithm) -> String {
        encode(
            &Header::new(alg),
            &claims,
            &EncodingKey::from_secret(secret.as_bytes()),
        )
        .unwrap()
    }

    #[allow(clippy::needless_pass_by_value)]
    fn base(extra: Value) -> Value {
        let mut v = json!({"id": "abc", "sub": "a@example.test", "typ": "access", "sid": "s1",
                           "exp": now() + 600, "roles": ["X"], "plan": "FREE"});
        for (k, val) in extra.as_object().unwrap() {
            v[k] = val.clone();
        }
        v
    }

    #[test]
    fn accepts_every_ring_member() {
        for member in members() {
            let t = sign(base(json!({})), &member, Algorithm::HS256);
            assert!(user_from_access_token(Some(&t), &ring()).is_some());
        }
        let t = sign(base(json!({})), &"z".repeat(40), Algorithm::HS256);
        assert!(user_from_access_token(Some(&t), &ring()).is_none());
    }

    #[test]
    fn algorithm_is_pinned() {
        let t = sign(base(json!({})), &members()[0], Algorithm::HS512);
        assert!(user_from_access_token(Some(&t), &ring()).is_none());
    }

    /// A token with exactly this header text, signed (HMAC-SHA256, whatever
    /// `alg` says) with `secret` unless `secret` is `None`.
    fn forge(header: &str, claims: &Value, secret: Option<&str>) -> String {
        use base64::Engine;
        use base64::engine::general_purpose::URL_SAFE_NO_PAD as B64;
        let input = format!(
            "{}.{}",
            B64.encode(header),
            B64.encode(serde_json::to_vec(claims).unwrap())
        );
        let signature = secret.map_or_else(String::new, |s| {
            jsonwebtoken::crypto::sign(
                input.as_bytes(),
                &EncodingKey::from_secret(s.as_bytes()),
                Algorithm::HS256,
            )
            .unwrap()
        });
        format!("{input}.{signature}")
    }

    fn accepted(token: &str) -> bool {
        user_from_access_token(Some(token), &ring()).is_some()
    }

    #[test]
    fn a_valid_token_is_accepted_and_a_changed_signature_is_not() {
        let t = sign(base(json!({})), &members()[0], Algorithm::HS256);
        assert!(accepted(&t));
        let (rest, sig) = t.rsplit_once('.').unwrap();
        // a different first character is a different first byte
        let first = if sig.starts_with('B') { "C" } else { "B" };
        assert!(!accepted(&format!("{rest}.{first}{}", &sig[1..])));
        // cut short, empty, and no signature part at all
        assert!(!accepted(&format!("{rest}.{}", &sig[..sig.len() - 8])));
        assert!(!accepted(&format!("{rest}.")));
        assert!(!accepted(rest));
        // the last of the 43 characters carries two unused bits: the same
        // bytes behind a different text are refused (PyJWT 2.x refuses them too)
        let alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
        let last = sig.chars().last().unwrap();
        let twin = alphabet
            .chars()
            .nth(alphabet.find(last).unwrap() ^ 1)
            .unwrap();
        assert!(!accepted(&format!(
            "{rest}.{}{twin}",
            &sig[..sig.len() - 1]
        )));
        // a longer signature than the MAC
        assert!(!accepted(&format!("{t}AAAA")));
    }

    #[test]
    fn the_previous_key_of_the_ring_verifies_and_an_unknown_key_does_not() {
        let claims = base(json!({}));
        let previous = sign(claims.clone(), &members()[1], Algorithm::HS256);
        assert!(accepted(&previous));
        let unknown = sign(claims, &"z".repeat(40), Algorithm::HS256);
        assert!(!accepted(&unknown));
        // a ring of one key refuses what the second key signed
        let single = KeyRing::from_members(vec![members()[0].clone()]);
        assert!(user_from_access_token(Some(&previous), &single).is_none());
    }

    #[test]
    fn alg_none_is_refused_signed_or_not() {
        let claims = base(json!({}));
        let key = members()[0].clone();
        for header in [
            r#"{"alg":"none","typ":"JWT"}"#,
            r#"{"alg":"None","typ":"JWT"}"#,
            r#"{"alg":"NONE","typ":"JWT"}"#,
        ] {
            assert!(!accepted(&forge(header, &claims, None)), "{header}");
            assert!(!accepted(&forge(header, &claims, Some(&key))), "{header}");
        }
    }

    #[test]
    fn a_missing_null_or_lower_case_alg_is_refused_even_with_a_valid_mac() {
        let claims = base(json!({}));
        let key = members()[0].clone();
        for header in [
            r#"{"typ":"JWT"}"#,
            r#"{"alg":null,"typ":"JWT"}"#,
            r#"{"alg":"hs256","typ":"JWT"}"#,
            r#"{"alg":"","typ":"JWT"}"#,
            "{}",
        ] {
            assert!(!accepted(&forge(header, &claims, Some(&key))), "{header}");
        }
        // control: the same bytes with the proper header are accepted
        assert!(accepted(&forge(
            r#"{"alg":"HS256","typ":"JWT"}"#,
            &claims,
            Some(&key)
        )));
    }

    #[test]
    fn an_asymmetric_or_other_hmac_alg_is_refused_even_with_a_valid_mac() {
        // algorithm confusion: the MAC is valid under the real key, the header
        // names another algorithm
        let claims = base(json!({}));
        let key = members()[0].clone();
        for alg in ["RS256", "ES256", "PS256", "EdDSA", "HS384", "HS512"] {
            let header = format!(r#"{{"alg":"{alg}","typ":"JWT"}}"#);
            assert!(!accepted(&forge(&header, &claims, Some(&key))), "{alg}");
        }
        // the classic form: a public key as the HMAC secret behind alg RS256
        let public_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----\n";
        let t = forge(r#"{"alg":"RS256","typ":"JWT"}"#, &claims, Some(public_key));
        assert!(!accepted(&t));
        // and the same secret under the proper alg is simply an unknown key
        let t = forge(r#"{"alg":"HS256","typ":"JWT"}"#, &claims, Some(public_key));
        assert!(!accepted(&t));
    }

    #[test]
    fn rejects_expired_and_not_yet_valid() {
        let t = sign(
            base(json!({"exp": now() - 5})),
            &members()[0],
            Algorithm::HS256,
        );
        assert!(user_from_access_token(Some(&t), &ring()).is_none());
        let t = sign(
            base(json!({"nbf": now() + 3600})),
            &members()[0],
            Algorithm::HS256,
        );
        assert!(user_from_access_token(Some(&t), &ring()).is_none());
        let t = sign(
            base(json!({"iat": now() + 3600})),
            &members()[0],
            Algorithm::HS256,
        );
        assert!(user_from_access_token(Some(&t), &ring()).is_none());
    }

    #[test]
    fn time_claims_are_read_as_pyjwt_reads_them() {
        let live = now() + 3600;
        let past = now() - 3600;
        // (claim, value, token accepted?)
        let cases = [
            ("exp", json!(live as f64 + 0.5), true),
            ("exp", json!(past as f64 + 0.5), false),
            ("exp", json!(live.to_string()), true),
            ("exp", json!(format!(" +{live} ")), true),
            ("exp", json!(past.to_string()), false),
            ("exp", json!("soon"), false),
            ("exp", json!("1.5"), false),
            ("exp", json!(""), false),
            ("exp", json!(null), false),
            ("exp", json!([live]), false),
            ("exp", json!({"a": live}), false),
            ("exp", json!(true), false), // int(True) = 1: long expired
            ("exp", json!("9_999_999_999"), true),
            ("exp", json!("_9999999999"), false),
            ("nbf", json!(live as f64 + 0.5), false),
            ("nbf", json!(live.to_string()), false),
            ("nbf", json!(past as f64 + 0.5), true),
            ("nbf", json!(past.to_string()), true),
            ("nbf", json!("soon"), false),
            ("nbf", json!(null), false),
            ("iat", json!(past as f64 + 0.5), true),
            ("iat", json!(live as f64), false),
            ("iat", json!(-5), true), // PyJWT accepts a negative `iat`
            ("iat", json!("now"), false),
        ];
        for (claim, value, accepted) in cases {
            let t = sign(
                base(json!({ claim: value.clone() })),
                &members()[0],
                Algorithm::HS256,
            );
            assert_eq!(
                user_from_access_token(Some(&t), &ring()).is_some(),
                accepted,
                "{claim} = {value}"
            );
        }
    }

    #[test]
    fn exp_equal_to_now_is_expired_and_nbf_equal_to_now_is_valid() {
        let claims = |name: &str, v: u64| {
            let mut c = Map::new();
            c.insert(name.to_string(), json!(v));
            c
        };
        assert!(!time_claims_hold(&claims("exp", 100), 100.0));
        assert!(time_claims_hold(&claims("exp", 101), 100.0));
        assert!(time_claims_hold(&claims("nbf", 100), 100.0));
        assert!(!time_claims_hold(&claims("nbf", 101), 100.0));
        assert!(time_claims_hold(&Map::new(), 100.0));
    }

    #[test]
    fn a_token_without_exp_is_accepted_like_pyjwt_does() {
        let mut c = base(json!({}));
        c.as_object_mut().unwrap().remove("exp");
        let t = sign(c, &members()[0], Algorithm::HS256);
        assert!(user_from_access_token(Some(&t), &ring()).is_some());
    }

    #[test]
    fn typ_and_sid_are_required() {
        for extra in [
            json!({"typ": "refresh"}),
            json!({"typ": null}),
            json!({"sid": ""}),
            json!({"sid": null}),
        ] {
            let t = sign(base(extra.clone()), &members()[0], Algorithm::HS256);
            assert!(
                user_from_access_token(Some(&t), &ring()).is_none(),
                "{extra}"
            );
        }
        let mut c = base(json!({}));
        c.as_object_mut().unwrap().remove("sid");
        assert!(
            user_from_access_token(Some(&sign(c, &members()[0], Algorithm::HS256)), &ring())
                .is_none()
        );
    }

    #[test]
    fn audience_claim_is_refused() {
        let t = sign(base(json!({"aud": "x"})), &members()[0], Algorithm::HS256);
        assert!(user_from_access_token(Some(&t), &ring()).is_none());
    }

    #[test]
    fn wrongly_typed_user_claims_are_refused() {
        for extra in [
            json!({"id": 5}),
            json!({"plan": "GOLD"}),
            json!({"roles": "x"}),
            json!({"mfa": "maybe"}),
        ] {
            let t = sign(base(extra.clone()), &members()[0], Algorithm::HS256);
            assert!(
                user_from_access_token(Some(&t), &ring()).is_none(),
                "{extra}"
            );
        }
    }

    #[test]
    fn garbage_and_empty_are_no_user() {
        assert!(user_from_access_token(None, &ring()).is_none());
        assert!(user_from_access_token(Some(""), &ring()).is_none());
        assert!(user_from_access_token(Some("not.a.jwt"), &ring()).is_none());
    }

    #[test]
    fn cookie_parser_matches_starlette() {
        let c = parse_cookies("a=1; Authorization=\"x y\"; RefreshToken=r; a=2; novalue");
        assert_eq!(c["a"], "2");
        assert_eq!(c["Authorization"], "x y");
        assert_eq!(c["RefreshToken"], "r");
        assert_eq!(c[""], "novalue");
    }
}
