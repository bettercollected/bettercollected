//! The error bodies of the Python backend, as a Rust route must produce them.
//!
//! * `backend/app/exceptions/http.py`: `HTTPException(status, content)`: the
//!   body is `content` as JSON (often a bare JSON string).
//! * FastAPI's own `{"detail": ...}` (404, 405, 422).
//! * `common/exceptions/validation.py`: the 422 body without the submitted
//!   values.
//! * `middlewares/__init__.py`: an unhandled error answers a plain-text 500.

use axum::body::Body;
use axum::http::{HeaderValue, StatusCode, header};
use axum::response::Response;
use serde_json::{Value, json};

/// A JSON response (`application/json`, no charset: as Starlette sends it).
pub fn json_response(status: StatusCode, body: &Value) -> Response {
    let bytes = serde_json::to_vec(body).unwrap_or_default();
    let mut response = Response::new(Body::from(bytes));
    *response.status_mut() = status;
    response.headers_mut().insert(
        header::CONTENT_TYPE,
        HeaderValue::from_static("application/json"),
    );
    response
}

/// The backend's `HTTPException(status, "message")`: the bare JSON string.
pub fn http_error(status: StatusCode, message: &str) -> Response {
    json_response(status, &Value::String(message.to_string()))
}

/// The backend's `HTTPException(status, {...})`: any JSON content.
pub fn http_exception(status: StatusCode, content: &Value) -> Response {
    json_response(status, content)
}

/// FastAPI's `{"detail": "message"}`.
pub fn detail(status: StatusCode, message: &str) -> Response {
    json_response(status, &json!({ "detail": message }))
}

/// One entry of the 422 `detail` list.
pub fn validation_item(loc: &[&str], msg: &str, kind: &str) -> Value {
    json!({ "loc": loc, "msg": msg, "type": kind })
}

/// The 422 of `request_validation_error_handler`: only `loc`, `msg` and `type`
/// per entry, never the submitted value.
pub fn validation_error(items: &[Value]) -> Response {
    json_response(
        StatusCode::UNPROCESSABLE_ENTITY,
        &json!({ "detail": items }),
    )
}

/// The 422 FastAPI answers for a path or query value that is not a 24-hex id
/// (`PydanticObjectId`).
pub fn invalid_object_id(location: &str, name: &str) -> Response {
    validation_error(&[validation_item(
        &[location, name],
        "Value error, Id must be of type PydanticObjectId",
        "value_error",
    )])
}

/// A plain-text response.
pub fn plain(status: StatusCode, text: &'static str) -> Response {
    let mut response = Response::new(Body::from(text));
    *response.status_mut() = status;
    response.headers_mut().insert(
        header::CONTENT_TYPE,
        HeaderValue::from_static("text/plain; charset=utf-8"),
    );
    response
}

/// What the backend answers when a request handler fails unexpectedly
/// (`base_exception_handler`): a plain-text 500 that says nothing of the cause.
pub fn internal_error() -> Response {
    plain(StatusCode::INTERNAL_SERVER_ERROR, "Internal server error")
}

/// A valid ObjectId text: 24 hexadecimal characters (`ObjectId.is_valid`).
pub fn is_object_id(value: &str) -> bool {
    value.len() == 24 && value.bytes().all(|b| b.is_ascii_hexdigit())
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::to_bytes;

    async fn body(response: Response) -> (StatusCode, String, Option<String>) {
        let status = response.status();
        let content_type = response
            .headers()
            .get(header::CONTENT_TYPE)
            .and_then(|v| v.to_str().ok())
            .map(str::to_string);
        let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
        (
            status,
            String::from_utf8(bytes.to_vec()).unwrap(),
            content_type,
        )
    }

    #[tokio::test]
    async fn an_http_exception_is_a_bare_json_string() {
        let (status, text, ct) =
            body(http_error(StatusCode::UNAUTHORIZED, "No user logged in.")).await;
        assert_eq!(status, StatusCode::UNAUTHORIZED);
        assert_eq!(text, r#""No user logged in.""#);
        assert_eq!(ct.as_deref(), Some("application/json"));
    }

    #[tokio::test]
    async fn detail_and_validation_shapes_match_fastapi() {
        let (_, text, _) = body(detail(StatusCode::NOT_FOUND, "Not Found")).await;
        assert_eq!(text, r#"{"detail":"Not Found"}"#);
        let (status, text, _) = body(invalid_object_id("path", "workspace_id")).await;
        assert_eq!(status, StatusCode::UNPROCESSABLE_ENTITY);
        let parsed: Value = serde_json::from_str(&text).unwrap();
        assert_eq!(
            parsed,
            json!({"detail":[{"loc":["path","workspace_id"],
                "msg":"Value error, Id must be of type PydanticObjectId","type":"value_error"}]})
        );
    }

    #[tokio::test]
    async fn an_unexpected_failure_says_nothing_of_the_cause() {
        let (status, text, ct) = body(internal_error()).await;
        assert_eq!(status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(text, "Internal server error");
        assert_eq!(ct.as_deref(), Some("text/plain; charset=utf-8"));
    }

    #[test]
    fn object_ids_are_24_hex_characters() {
        assert!(is_object_id("6a0000000000000000000001"));
        assert!(is_object_id("6A0000000000000000000001"));
        assert!(!is_object_id("6a000000000000000000000"));
        assert!(!is_object_id("g".repeat(24).as_str()));
        assert!(!is_object_id("é0000000000000000000001"));
    }
}
