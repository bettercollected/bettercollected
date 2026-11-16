//! The pass-through: every request the Rust side does not serve is forwarded
//! to the Python backend (`BC_PYTHON_UPSTREAM`) and its answer is returned as
//! it is.
//!
//! What is forwarded: the method, the path and query, every header except the
//! hop-by-hop ones (RFC 9110 7.6.1 and anything the `Connection` header
//! names), the original `Host` (the backend builds redirects from it) and the
//! body, streamed in both directions without buffering. `X-Forwarded-For` has
//! the TCP peer appended; the backend decides whom to believe from its own
//! `TRUSTED_PROXIES`, which must therefore name this service's address.
//!
//! What is not: `Upgrade`/WebSocket (the backend serves none), `Expect`
//! (this side already answered it), `Content-Length` of the request (the
//! client computes it again from the streamed body, so it can never disagree
//! with `Transfer-Encoding`), redirects (never followed: a `Location` is the
//! client's to act on).
//!
//! Timeouts (no proxy configuration in the repository states any, so these are
//! this service's own): 5 s to connect; the upstream has 120 s to answer with
//! its headers; no more than 120 s of silence between two chunks of a body, in
//! either direction. Both are settings (`BC_PYTHON_UPSTREAM_CONNECT_TIMEOUT_SECS`,
//! `BC_PYTHON_UPSTREAM_TIMEOUT_SECS`). A slow export that keeps sending is
//! never cut; a stalled one is. The pooled upstream connections are dropped
//! after 3 s idle, below uvicorn's 5 s keep-alive, so a request never lands on
//! a connection the backend has just closed.
//!
//! Logging: a failure logs the method and the path with receipt numbers
//! redacted, and the kind of failure. Never the query string, a header, a
//! cookie, a body or the client's address (the rules of
//! `middlewares/request_privacy.py`).

use std::net::SocketAddr;
use std::pin::Pin;
use std::task::{Context, Poll};
use std::time::Duration;

use axum::body::{Body, Bytes};
use axum::extract::{ConnectInfo, Request};
use axum::http::header::{self, HeaderName};
use axum::http::{HeaderMap, HeaderValue, StatusCode, Uri, uri::PathAndQuery};
use axum::response::Response;
use bc_http::client_ip::{MAX_FORWARDED_HOPS, MAX_HEADER_LENGTH};
use bc_http::error::plain;
use bc_http::privacy::loggable_request;
use hyper::body::{Body as HttpBody, Frame, SizeHint};
use hyper_util::client::legacy::Client;
use hyper_util::client::legacy::connect::HttpConnector;
use hyper_util::rt::TokioExecutor;
use tokio::time::{Instant, Sleep};

type BoxError = Box<dyn std::error::Error + Send + Sync>;

/// Header names that are never forwarded (RFC 9110 7.6.1, plus `Proxy-Connection`).
const HOP_BY_HOP: [&str; 9] = [
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
];

/// Marks a response that came from the Python backend: it already carries the
/// backend's own CORS and caching headers, so the Rust-side layers leave it
/// alone.
#[derive(Debug, Clone, Copy)]
pub struct FromUpstream;

/// A body that fails when nothing arrives for `timeout`.
struct IdleBody {
    inner: Body,
    timeout: Duration,
    sleep: Pin<Box<Sleep>>,
}

impl std::fmt::Debug for IdleBody {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("IdleBody")
            .field("timeout", &self.timeout)
            .finish_non_exhaustive()
    }
}

impl IdleBody {
    fn new(inner: Body, timeout: Duration) -> IdleBody {
        IdleBody {
            inner,
            timeout,
            sleep: Box::pin(tokio::time::sleep(timeout)),
        }
    }
}

impl HttpBody for IdleBody {
    type Data = Bytes;
    type Error = BoxError;

    fn poll_frame(
        mut self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Option<Result<Frame<Bytes>, BoxError>>> {
        let this = &mut *self;
        match Pin::new(&mut this.inner).poll_frame(cx) {
            Poll::Ready(item) => {
                let next = Instant::now() + this.timeout;
                this.sleep.as_mut().reset(next);
                Poll::Ready(item.map(|r| r.map_err(Into::into)))
            }
            Poll::Pending => match this.sleep.as_mut().poll(cx) {
                Poll::Ready(()) => Poll::Ready(Some(Err("no data within the time allowed".into()))),
                Poll::Pending => Poll::Pending,
            },
        }
    }

    fn is_end_stream(&self) -> bool {
        self.inner.is_end_stream()
    }

    fn size_hint(&self) -> SizeHint {
        self.inner.size_hint()
    }
}

/// The forwarding client.
pub struct Proxy {
    client: Client<HttpConnector, IdleBody>,
    /// `host[:port]` of the upstream.
    authority: String,
    idle_timeout: Duration,
    served_by_header: bool,
}

impl std::fmt::Debug for Proxy {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Proxy")
            .field("idle_timeout", &self.idle_timeout)
            .finish_non_exhaustive()
    }
}

impl Proxy {
    /// `upstream`: `http://host[:port]` (already checked by `bc-config`).
    pub fn new(
        upstream: &str,
        connect_timeout: Duration,
        idle_timeout: Duration,
        served_by_header: bool,
    ) -> Proxy {
        let mut connector = HttpConnector::new();
        connector.set_connect_timeout(Some(connect_timeout));
        connector.set_nodelay(true);
        let client = Client::builder(TokioExecutor::new())
            .pool_idle_timeout(Duration::from_secs(3))
            .build(connector);
        Proxy {
            client,
            authority: upstream
                .strip_prefix("http://")
                .unwrap_or(upstream)
                .to_string(),
            idle_timeout,
            served_by_header,
        }
    }

    /// Forwards `request` and returns the upstream's answer. Never panics and
    /// never returns an upstream error's text: a failure is a 502 (could not
    /// reach or talk to the backend) or a 504 (it did not answer in time).
    pub async fn forward(&self, request: Request) -> Response {
        let (parts, body) = request.into_parts();
        let peer = parts
            .extensions
            .get::<ConnectInfo<SocketAddr>>()
            .map(|c| c.0);
        let log_line = loggable_request(parts.method.as_str(), parts.uri.path());

        let path_and_query = parts
            .uri
            .path_and_query()
            .cloned()
            .unwrap_or_else(|| PathAndQuery::from_static("/"));
        let Ok(uri) = Uri::builder()
            .scheme("http")
            .authority(self.authority.as_str())
            .path_and_query(path_and_query)
            .build()
        else {
            tracing::error!("upstream address cannot be built: {log_line}");
            return bad_gateway();
        };

        let mut outgoing = axum::http::Request::new(IdleBody::new(body, self.idle_timeout));
        *outgoing.method_mut() = parts.method;
        *outgoing.uri_mut() = uri;
        *outgoing.version_mut() = axum::http::Version::HTTP_11;
        *outgoing.headers_mut() = request_headers(&parts.headers, peer);

        let answered = tokio::time::timeout(self.idle_timeout, self.client.request(outgoing)).await;
        let response = match answered {
            Err(_elapsed) => {
                tracing::warn!("upstream timeout (headers): {log_line}");
                return gateway(StatusCode::GATEWAY_TIMEOUT, "Gateway Timeout");
            }
            Ok(Err(error)) => {
                // the kind only: an error's text can name addresses
                let kind = if error.is_connect() {
                    "connect"
                } else {
                    "request"
                };
                tracing::warn!("upstream {kind} failed: {log_line}");
                return bad_gateway();
            }
            Ok(Ok(response)) => response,
        };

        let (head, incoming) = response.into_parts();
        let mut out = Response::new(Body::new(IdleBody::new(
            Body::new(incoming),
            self.idle_timeout,
        )));
        *out.status_mut() = head.status;
        *out.headers_mut() = response_headers(&head.headers);
        if self.served_by_header {
            out.headers_mut().insert(
                HeaderName::from_static("x-bc-served-by"),
                HeaderValue::from_static("python"),
            );
        }
        out.extensions_mut().insert(FromUpstream);
        out
    }
}

fn gateway(status: StatusCode, text: &'static str) -> Response {
    plain(status, text)
}

fn bad_gateway() -> Response {
    gateway(StatusCode::BAD_GATEWAY, "Bad Gateway")
}

/// The names a `Connection` header lists: they are hop-by-hop too.
fn connection_listed(headers: &HeaderMap) -> Vec<HeaderName> {
    headers
        .get_all(header::CONNECTION)
        .iter()
        .filter_map(|v| v.to_str().ok())
        .flat_map(|v| v.split(','))
        .filter_map(|name| HeaderName::from_bytes(name.trim().as_bytes()).ok())
        .collect()
}

fn is_hop_by_hop(name: &HeaderName, listed: &[HeaderName]) -> bool {
    HOP_BY_HOP.contains(&name.as_str()) || listed.contains(name)
}

/// The headers sent upstream: all but the hop-by-hop ones, `Expect` and
/// `Content-Length`, with the peer appended to `X-Forwarded-For`.
pub fn request_headers(incoming: &HeaderMap, peer: Option<SocketAddr>) -> HeaderMap {
    let listed = connection_listed(incoming);
    let mut out = HeaderMap::with_capacity(incoming.len() + 1);
    for (name, value) in incoming {
        if is_hop_by_hop(name, &listed)
            || name == header::EXPECT
            || name == header::CONTENT_LENGTH
            || name.as_str() == "x-forwarded-for"
        {
            continue;
        }
        out.append(name.clone(), value.clone());
    }
    if let Some(chain) = forwarded_chain(incoming, peer)
        && let Ok(value) = HeaderValue::from_str(&chain)
    {
        out.insert(HeaderName::from_static("x-forwarded-for"), value);
    }
    out
}

/// The headers returned to the client: all but the hop-by-hop ones. Repeated
/// headers (several `Set-Cookie`) stay repeated.
pub fn response_headers(upstream: &HeaderMap) -> HeaderMap {
    let listed = connection_listed(upstream);
    let mut out = HeaderMap::with_capacity(upstream.len());
    for (name, value) in upstream {
        if !is_hop_by_hop(name, &listed) {
            out.append(name.clone(), value.clone());
        }
    }
    out
}

/// `X-Forwarded-For` with the TCP peer appended: every incoming value in
/// order, then the peer. Only the last [`MAX_FORWARDED_HOPS`] entries are kept
/// and the value stays under [`MAX_HEADER_LENGTH`] (the backend ignores a
/// longer header altogether), dropping from the left: the left of the chain is
/// the client's to write, the right is ours. `None` without a peer address and
/// without an incoming chain.
fn forwarded_chain(incoming: &HeaderMap, peer: Option<SocketAddr>) -> Option<String> {
    let mut hops: Vec<String> = incoming
        .get_all("x-forwarded-for")
        .iter()
        .flat_map(|v| {
            // the chain may hold bytes that are not UTF-8: read them lossily
            let text = String::from_utf8_lossy(v.as_bytes()).into_owned();
            text.split(',').map(str::to_string).collect::<Vec<_>>()
        })
        .map(|h| h.trim().to_string())
        .filter(|h| !h.is_empty())
        .collect();
    if let Some(peer) = peer {
        hops.push(peer.ip().to_canonical().to_string());
    }
    if hops.is_empty() {
        return None;
    }
    let start = hops.len().saturating_sub(MAX_FORWARDED_HOPS);
    let mut hops = hops.split_off(start);
    while hops.len() > 1 && hops.join(", ").len() > MAX_HEADER_LENGTH {
        hops.remove(0);
    }
    Some(hops.join(", "))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn headers(pairs: &[(&str, &str)]) -> HeaderMap {
        let mut h = HeaderMap::new();
        for (k, v) in pairs {
            h.append(
                HeaderName::from_bytes(k.as_bytes()).unwrap(),
                HeaderValue::from_str(v).unwrap(),
            );
        }
        h
    }

    #[allow(clippy::unnecessary_wraps)]
    fn peer(s: &str) -> Option<SocketAddr> {
        Some(s.parse().unwrap())
    }

    #[test]
    fn hop_by_hop_headers_and_those_named_by_connection_are_dropped() {
        let incoming = headers(&[
            ("connection", "keep-alive, x-private"),
            ("keep-alive", "timeout=5"),
            ("x-private", "1"),
            ("te", "trailers"),
            ("upgrade", "websocket"),
            ("transfer-encoding", "chunked"),
            ("proxy-authorization", "Basic x"),
            ("expect", "100-continue"),
            ("content-length", "5"),
            ("host", "app.example.test"),
            ("cookie", "a=1"),
            ("cookie", "b=2"),
            ("authorization", "Bearer t"),
            ("x-custom", "kept"),
        ]);
        let out = request_headers(&incoming, peer("203.0.113.5:4000"));
        let names: Vec<&str> = out.keys().map(HeaderName::as_str).collect();
        for gone in [
            "connection",
            "keep-alive",
            "x-private",
            "te",
            "upgrade",
            "transfer-encoding",
            "proxy-authorization",
            "expect",
            "content-length",
        ] {
            assert!(!names.contains(&gone), "{gone} was forwarded");
        }
        assert_eq!(out["host"], "app.example.test");
        assert_eq!(out["authorization"], "Bearer t");
        assert_eq!(out["x-custom"], "kept");
        assert_eq!(
            out.get_all("cookie").iter().count(),
            2,
            "repeated headers stay repeated"
        );
    }

    #[test]
    fn the_peer_is_appended_to_forwarded_for() {
        let none = request_headers(&HeaderMap::new(), peer("203.0.113.5:1"));
        assert_eq!(none["x-forwarded-for"], "203.0.113.5");
        let one = request_headers(
            &headers(&[("x-forwarded-for", "198.51.100.1")]),
            peer("10.0.0.2:1"),
        );
        assert_eq!(one["x-forwarded-for"], "198.51.100.1, 10.0.0.2");
        // several headers are one list, in order
        let two = request_headers(
            &headers(&[
                ("x-forwarded-for", "6.6.6.6, 198.51.100.1"),
                ("x-forwarded-for", "10.0.0.9"),
            ]),
            peer("10.0.0.2:1"),
        );
        assert_eq!(
            two["x-forwarded-for"],
            "6.6.6.6, 198.51.100.1, 10.0.0.9, 10.0.0.2"
        );
        assert_eq!(two.get_all("x-forwarded-for").iter().count(), 1);
        // IPv6 and IPv4-mapped peers
        let v6 = request_headers(&HeaderMap::new(), peer("[2001:db8::7]:1"));
        assert_eq!(v6["x-forwarded-for"], "2001:db8::7");
        let mapped = request_headers(&HeaderMap::new(), peer("[::ffff:192.0.2.1]:1"));
        assert_eq!(mapped["x-forwarded-for"], "192.0.2.1");
        // no peer, no chain: nothing invented
        assert!(
            request_headers(&HeaderMap::new(), None)
                .get("x-forwarded-for")
                .is_none()
        );
    }

    #[test]
    fn a_long_chain_loses_its_client_written_left_side_and_keeps_ours() {
        let many = (0..40)
            .map(|i| format!("192.0.2.{i}"))
            .collect::<Vec<_>>()
            .join(", ");
        let out = request_headers(&headers(&[("x-forwarded-for", &many)]), peer("10.0.0.2:1"));
        let value = out["x-forwarded-for"].to_str().unwrap();
        assert_eq!(value.split(", ").count(), MAX_FORWARDED_HOPS);
        assert!(value.ends_with("192.0.2.39, 10.0.0.2"), "{value}");
        // an oversize value is cut from the left until the backend would read it
        let huge = "9".repeat(5000);
        let out = request_headers(&headers(&[("x-forwarded-for", &huge)]), peer("10.0.0.2:1"));
        assert_eq!(out["x-forwarded-for"], "10.0.0.2");
    }

    #[test]
    fn response_headers_keep_every_set_cookie() {
        let upstream = headers(&[
            ("set-cookie", "Authorization=a; Path=/"),
            ("set-cookie", "RefreshToken=b; Path=/"),
            ("connection", "close"),
            ("keep-alive", "timeout=5"),
            ("transfer-encoding", "chunked"),
            ("cache-control", "no-store"),
            ("content-length", "3"),
        ]);
        let out = response_headers(&upstream);
        assert_eq!(out.get_all("set-cookie").iter().count(), 2);
        assert_eq!(out["cache-control"], "no-store");
        assert_eq!(out["content-length"], "3");
        for gone in ["connection", "keep-alive", "transfer-encoding"] {
            assert!(out.get(gone).is_none(), "{gone}");
        }
    }
}
