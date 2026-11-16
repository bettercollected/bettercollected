#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::cast_possible_truncation
)]
//! The body-nesting rule against the vectors the Python code writes
//! (`contract/golden_depth.py`): the whole-value check and the piecewise scanner
//! agree with `too_deep` / `DepthScanner` of `backend/app/utils/json_depth.py` on
//! every body, however it is cut into pieces.

use axum::http::{HeaderMap, HeaderValue, Method, header};
use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use bc_http::json_depth::{
    self, CODE, DepthScanner, MAX_BUFFERED_BYTES, MAX_JSON_DEPTH, carries_json, too_deep,
};
use serde_json::Value;

fn vectors() -> Value {
    serde_json::from_str(include_str!("golden/json_depth.json")).unwrap()
}

fn body_of(case: &Value) -> Vec<u8> {
    let mut body = Vec::new();
    for part in case["parts"].as_array().unwrap() {
        let piece = STANDARD.decode(part[0].as_str().unwrap()).unwrap();
        for _ in 0..part[1].as_u64().unwrap() {
            body.extend_from_slice(&piece);
        }
    }
    assert_eq!(body.len() as u64, case["bytes"].as_u64().unwrap());
    body
}

#[test]
fn the_constants_are_the_ones_python_defines() {
    let v = vectors();
    assert_eq!(v["limit"].as_u64().unwrap(), MAX_JSON_DEPTH as u64);
    assert_eq!(MAX_JSON_DEPTH, 128);
    assert_eq!(v["code"].as_str().unwrap(), CODE);
    assert_eq!(v["message"].as_str().unwrap(), json_depth::message());
    assert_eq!(v["buffered"].as_u64().unwrap(), MAX_BUFFERED_BYTES as u64);
}

#[test]
fn the_whole_value_check_equals_pythons_on_every_body() {
    let v = vectors();
    let cases = v["cases"].as_array().unwrap();
    assert!(cases.len() >= 40);
    let mut deep = 0;
    for case in cases {
        let expect = case["too_deep"].as_bool().unwrap();
        deep += usize::from(expect);
        assert_eq!(
            too_deep(&body_of(case), MAX_JSON_DEPTH),
            expect,
            "{}",
            case["name"]
        );
    }
    assert!(deep > 10 && deep < cases.len());
}

#[test]
fn the_piecewise_scanner_equals_pythons_however_the_body_is_cut() {
    let v = vectors();
    for case in v["cases"].as_array().unwrap() {
        let body = body_of(case);
        let expect = case["too_deep"].as_bool().unwrap();
        let sizes: &[usize] = if body.len() > 200_000 {
            &[7, 4096, 65_536]
        } else {
            &[1, 2, 3, 7, 4096]
        };
        for &size in sizes {
            let mut scanner = DepthScanner::default();
            let got = body.chunks(size).any(|piece| scanner.feed(piece));
            assert_eq!(got, expect, "{} in pieces of {size}", case["name"]);
        }
    }
}

#[test]
fn a_backslash_ending_a_piece_escapes_the_first_byte_of_the_next() {
    // the string `"\"` + `]]]`: the quote is escaped, so the string is still open
    let mut scanner = DepthScanner::new(1);
    assert!(!scanner.feed(b"\"a\\"));
    assert!(!scanner.feed(b"\"[[[["));
    assert!(!scanner.feed(b"\"[")); // closes, then one level: not past 1
    assert!(scanner.feed(b"["));
}

#[test]
fn a_stray_closer_never_buys_levels() {
    let mut scanner = DepthScanner::new(2);
    assert!(!scanner.feed(b"]]]]]]]]"));
    assert!(!scanner.feed(b"[["));
    assert!(scanner.feed(b"["));
}

fn headers(pairs: &[(&str, &str)]) -> HeaderMap {
    let mut map = HeaderMap::new();
    for (k, v) in pairs {
        map.append(
            header::HeaderName::from_bytes(k.as_bytes()).unwrap(),
            HeaderValue::from_str(v).unwrap(),
        );
    }
    map
}

#[test]
fn which_requests_are_scanned_follows_the_python_middleware() {
    let some = |n: usize| Some(Some(n));
    let chunked = Some(None);
    let post = &Method::POST;
    // methods
    assert_eq!(
        carries_json(&Method::GET, &headers(&[("content-length", "5")])),
        None
    );
    assert_eq!(
        carries_json(&Method::HEAD, &headers(&[("content-length", "5")])),
        None
    );
    assert_eq!(
        carries_json(&Method::OPTIONS, &headers(&[("content-length", "5")])),
        None
    );
    for m in [Method::PUT, Method::PATCH, Method::DELETE, Method::POST] {
        assert_eq!(
            carries_json(&m, &headers(&[("content-length", "5")])),
            some(5)
        );
    }
    // no body declared
    assert_eq!(carries_json(post, &headers(&[])), None);
    assert_eq!(
        carries_json(post, &headers(&[("content-length", "0")])),
        None
    );
    assert_eq!(
        carries_json(post, &headers(&[("content-length", "abc")])),
        None
    );
    assert_eq!(
        carries_json(post, &headers(&[("content-length", "")])),
        None
    );
    // chunked
    assert_eq!(
        carries_json(post, &headers(&[("transfer-encoding", "chunked")])),
        chunked
    );
    assert_eq!(
        carries_json(
            post,
            &headers(&[("transfer-encoding", "chunked"), ("content-length", "x")])
        ),
        chunked
    );
    // a length beyond what fits is beyond the cap all the same
    assert_eq!(
        carries_json(
            post,
            &headers(&[("content-length", "99999999999999999999999999")])
        ),
        some(usize::MAX)
    );
    assert_eq!(
        carries_json(post, &headers(&[("content-length", " 12 ")])),
        some(12)
    );
    // media types
    let ct = |t: &str| {
        carries_json(
            post,
            &headers(&[("content-length", "5"), ("content-type", t)]),
        )
    };
    for yes in [
        "application/json",
        "Application/JSON; charset=utf-8",
        "text/plain",
        "text/plain;charset=UTF-8",
        "application/vnd.api+json",
        "application/scim+json",
        "application/problem+json; x=y",
        "",
        " application/json ",
    ] {
        assert_eq!(ct(yes), some(5), "{yes:?}");
    }
    for no in [
        "application/x-www-form-urlencoded",
        "multipart/form-data; boundary=x",
        "application/octet-stream",
        "text/html",
        "image/png",
        "application/jsonx",
        "text/json",
        "application/x+json+",
    ] {
        assert_eq!(ct(no), None, "{no:?}");
    }
}

#[test]
fn the_refusal_is_the_422_python_sends() {
    let response = json_depth::refusal("/api/v1/workspaces/x/forms");
    assert_eq!(response.status().as_u16(), 422);
    assert_eq!(
        response.headers().get(header::CONTENT_TYPE).unwrap(),
        "application/json"
    );
    let mcp = json_depth::refusal("/mcp/");
    assert_eq!(mcp.status().as_u16(), 422);
}
