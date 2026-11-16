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

fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_secs())
}

/// The claims of `token` when some member of the ring verifies it and the
/// time claims hold; `None` otherwise (Python's `decode_token` returns None
/// on any `PyJWTError`).
pub fn decode_with_ring(token: &str, ring: &KeyRing) -> Option<Map<String, Value>> {
    let mut validation = Validation::new(Algorithm::HS256);
    validation.leeway = 0;
    validation.validate_exp = true;
    validation.validate_nbf = true;
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
                // PyJWT: `iat` must be an integer and not in the future
                if let Some(iat) = claims.get("iat") {
                    match iat.as_i64() {
                        Some(v) if u64::try_from(v).is_ok_and(|v| v <= now()) => {}
                        _ => return None,
                    }
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
