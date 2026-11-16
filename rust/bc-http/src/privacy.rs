//! What the request log may say about a request, and which responses must never
//! be cached. A port of `backend/app/middlewares/request_privacy.py`.
//!
//! A receipt number (`/submissions/by-uuid/<number>`) opens a response's
//! answers without a sign-in, and the search box sends a respondent's email as
//! a query parameter. Neither may reach the logs, whose readers are wider than
//! the database's access rules. Log the method and the redacted path, never the
//! query string, a body, a cookie or the client's address.

use std::sync::LazyLock;

use axum::http::{HeaderName, HeaderValue};
use axum::response::Response;
use percent_encoding::percent_decode_str;
use regex::Regex;

pub const REDACTED: &str = "<redacted>";

/// `Cache-Control: no-store` and `Pragma: no-cache`.
pub const NO_STORE_HEADERS: [(&str, &str); 2] =
    [("cache-control", "no-store"), ("pragma", "no-cache")];

// the receipt number in the path of every by-uuid route
#[allow(clippy::expect_used)] // a constant pattern, proven by the tests
static RECEIPT_IN_TEXT: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r#"(/by-uuid/)[^/?#\s<>"']+"#).expect("static pattern"));
// defence in depth: a receipt number (a UUID) pasted where a response id goes
#[allow(clippy::expect_used)]
static RECEIPT_AS_RESPONSE_ID: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"(/submissions/)[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
    )
    .expect("static pattern")
});

// Routes whose body is decrypted respondent data.
#[allow(clippy::expect_used)]
static RESPONSE_DATA_PATH: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(concat!(
        r"/workspaces/[^/]+/(?:",
        r"(?:forms/[^/]+/)?",
        r"(?:submissions(?:/.*)?|all-submissions|submission-paths)",
        r"|forms/[^/]+/(?:ai/insights|exports)(?:/.*)?",
        r"|forms/[^/]+/drafts(?:/.*)?",
        r"|responders(?:/.*)?",
        r")/?$"
    ))
    .expect("static pattern")
});

/// `text` with the receipt number of any `by-uuid` path in it replaced, and
/// any UUID-shaped segment straight after `/submissions/`.
pub fn redact_receipts(text: &str) -> String {
    let text = RECEIPT_IN_TEXT.replace_all(text, format!("${{1}}{REDACTED}").as_str());
    // Python's `(?![0-9a-zA-Z-])` after the UUID, by hand: the regex crate has no lookahead
    let mut out = String::with_capacity(text.len());
    let mut last = 0;
    for m in RECEIPT_AS_RESPONSE_ID.find_iter(&text) {
        let follows = text[m.end()..].chars().next();
        if follows.is_some_and(|c| c.is_ascii_alphanumeric() || c == '-') {
            continue;
        }
        out.push_str(&text[last..m.start()]);
        out.push_str("/submissions/");
        out.push_str(REDACTED);
        last = m.end();
    }
    out.push_str(&text[last..]);
    out
}

/// How many times a path is percent-decoded for logging. The server decodes
/// once; more rounds also catch a path that is encoded twice, which the
/// backend does not route but which must not carry a receipt number into a log.
const DECODE_ROUNDS: usize = 3;

/// The path as it must be logged. The backend routes on the percent-decoded
/// path (`/submissions/by%2Duuid/<receipt>` reaches its receipt route, and so
/// does an encoded slash), so redaction works on the decoded path: decoded up to
/// [`DECODE_ROUNDS`] times, redacted, and stripped of control characters (a
/// decoded `%0A` must not start a forged log line).
pub fn loggable_path(path: &str) -> String {
    let mut text = path.to_string();
    for _ in 0..DECODE_ROUNDS {
        let decoded = percent_decode_str(&text).decode_utf8_lossy().into_owned();
        if decoded == text {
            break;
        }
        text = decoded;
    }
    redact_receipts(&text)
        .chars()
        .map(|c| if c.is_control() { '?' } else { c })
        .collect()
}

/// The request as it is logged: method and redacted path, never the query
/// string (search text, respondent emails).
pub fn loggable_request(method: &str, path: &str) -> String {
    format!("{method} {}", loggable_path(path))
}

/// Whether the response of `path` may hold decrypted answers, and so must not
/// be kept in a browser or proxy cache.
pub fn carries_response_data(path: &str) -> bool {
    RESPONSE_DATA_PATH.is_match(path)
}

/// Adds the no-store headers when the path carries response data.
pub fn apply_no_store(response: &mut Response, path: &str) {
    if carries_response_data(path) {
        for (name, value) in NO_STORE_HEADERS {
            response.headers_mut().insert(
                HeaderName::from_static(name),
                HeaderValue::from_static(value),
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_receipt_number_never_reaches_a_log_line() {
        assert_eq!(
            loggable_request("GET", "/api/v1/workspaces/w/submissions/by-uuid/abc-123"),
            "GET /api/v1/workspaces/w/submissions/by-uuid/<redacted>"
        );
        let uuid = "123e4567-e89b-12d3-a456-426614174000";
        assert_eq!(
            redact_receipts(&format!("/submissions/{uuid}")),
            "/submissions/<redacted>"
        );
        // a longer token is not a receipt number, a response id is not UUID-shaped
        let longer = format!("/submissions/{uuid}-more");
        assert_eq!(redact_receipts(&longer), longer);
        let id = "/submissions/6a0000000000000000000001";
        assert_eq!(redact_receipts(id), id);
    }

    #[test]
    fn an_encoded_path_is_redacted_as_the_backend_routes_it() {
        let uuid = "123e4567-e89b-12d3-a456-426614174000";
        for raw in [
            "/api/v1/workspaces/w/submissions/by%2Duuid/RECEIPT",
            "/api/v1/workspaces/w/submissions/by%2duuid/RECEIPT",
            "/api/v1/workspaces/w/submissions/b%79%2Duu%69d/RECEIPT",
            "/api/v1/workspaces/w/submissions/by-uuid%2FRECEIPT",
            "/api/v1/workspaces/w/submissions/by-uuid%2fRECEIPT",
            "/api/v1/workspaces/w/submissions/by%252Duuid/RECEIPT",
            "/api/v1/workspaces/w/submissions/by-uuid/RE%43EIPT",
        ] {
            let logged = loggable_request("GET", raw);
            assert!(
                !logged.contains("RECEIPT") && !logged.contains("EIPT"),
                "{raw}: {logged}"
            );
            assert!(logged.ends_with("/by-uuid/<redacted>"), "{raw}: {logged}");
        }
        let id = format!("/api/v1/workspaces/w/submissions%2F{uuid}");
        assert!(!loggable_request("GET", &id).contains(uuid));
        let id = format!("/api/v1/workspaces/w/%73ubmissions/{uuid}");
        assert!(!loggable_request("GET", &id).contains(uuid));
    }

    #[test]
    fn a_decoded_control_character_cannot_forge_a_log_line() {
        let logged = loggable_request("GET", "/a%0AINFO fake%0d%0aline");
        assert!(
            !logged.contains('\n') && !logged.contains('\r'),
            "{logged:?}"
        );
        assert_eq!(loggable_request("GET", "/plain/path"), "GET /plain/path");
        // bytes that are not UTF-8 do not stop the log line
        assert!(loggable_request("GET", "/x%FF").contains('\u{fffd}'));
    }

    #[test]
    fn response_data_paths_are_the_python_ones() {
        for yes in [
            "/api/v1/workspaces/w/submissions",
            "/api/v1/workspaces/w/submissions/",
            "/api/v1/workspaces/w/forms/f/submissions/s1",
            "/api/v1/workspaces/w/all-submissions",
            "/api/v1/workspaces/w/submission-paths",
            "/api/v1/workspaces/w/forms/f/ai/insights",
            "/api/v1/workspaces/w/forms/f/exports/e1",
            "/api/v1/workspaces/w/forms/f/drafts/d",
            "/api/v1/workspaces/w/responders",
        ] {
            assert!(carries_response_data(yes), "{yes}");
        }
        for no in [
            "/api/v1/workspaces/w/permissions",
            "/api/v1/workspaces/w/forms/f",
            "/api/v1/workspaces/w/submissionsx",
            "/health",
        ] {
            assert!(!carries_response_data(no), "{no}");
        }
    }

    #[test]
    fn no_store_is_added_only_where_answers_travel() {
        let mut r = Response::new(axum::body::Body::empty());
        apply_no_store(&mut r, "/api/v1/workspaces/w/responders");
        assert_eq!(r.headers()["cache-control"], "no-store");
        assert_eq!(r.headers()["pragma"], "no-cache");
        let mut r = Response::new(axum::body::Body::empty());
        apply_no_store(&mut r, "/api/v1/workspaces/w/permissions");
        assert!(r.headers().get("cache-control").is_none());
    }
}
