//! Settings of the edge itself (`BC_*`): the Python upstream every request
//! the Rust side does not serve is forwarded to, the per-group switch and the
//! upstream timeouts.

use std::time::Duration;

use crate::ConfigError;
use crate::source::Settings;

/// Time allowed to open a connection to the upstream.
pub const DEFAULT_CONNECT_TIMEOUT_SECS: u64 = 5;
/// Time allowed to the upstream to answer with its headers, and the longest
/// silence tolerated between two chunks of a body, in either direction.
pub const DEFAULT_IDLE_TIMEOUT_SECS: u64 = 120;

#[derive(Debug, Clone, PartialEq, Eq)]
#[allow(clippy::struct_excessive_bools)]
pub struct EdgeConfig {
    /// `BC_PYTHON_UPSTREAM`: `http://host[:port]` of the Python backend.
    /// Plain HTTP only: the hop is inside the deployment's own network.
    pub python_upstream: String,
    /// `BC_RUST_ROUTES`: the route groups the Rust side serves, comma
    /// separated. Empty (the default): every request goes to Python.
    pub rust_routes: Vec<String>,
    pub connect_timeout: Duration,
    pub idle_timeout: Duration,
    /// `BC_SERVED_BY_HEADER`: answer with `X-BC-Served-By: rust|python`.
    /// For the contract harness; off by default.
    pub served_by_header: bool,
}

fn seconds(settings: &Settings, name: &str, default: u64) -> Result<Duration, ConfigError> {
    match settings.get(name) {
        None => Ok(Duration::from_secs(default)),
        Some(raw) => raw
            .parse::<u64>()
            .ok()
            .filter(|n| (1..=3600).contains(n))
            .map(Duration::from_secs)
            .ok_or_else(|| ConfigError(format!("{name} is not a number of seconds (1 to 3600)"))),
    }
}

/// `http://host[:port]` and nothing else; the message never echoes the value
/// (an address can carry credentials).
fn check_upstream(value: &str) -> Result<String, ConfigError> {
    let bad = |why: &str| ConfigError(format!("BC_PYTHON_UPSTREAM {why}"));
    let rest = value
        .strip_prefix("http://")
        .ok_or_else(|| bad("must start with http:// (the upstream hop is plain HTTP)"))?;
    let rest = rest.strip_suffix('/').unwrap_or(rest);
    if rest.is_empty() || rest.contains(['/', '?', '#', '@', ' ']) || rest.starts_with(':') {
        return Err(bad(
            "must be http://host[:port] with no path, query or credentials",
        ));
    }
    if let Some((_, port)) = rest.rsplit_once(':')
        && !rest.ends_with(']')
        && port.parse::<u16>().is_err()
    {
        return Err(bad("has a port that is not a number"));
    }
    Ok(format!("http://{rest}"))
}

impl EdgeConfig {
    pub fn from_settings(settings: &Settings) -> Result<EdgeConfig, ConfigError> {
        let upstream = settings
            .get("BC_PYTHON_UPSTREAM")
            .ok_or_else(|| ConfigError("BC_PYTHON_UPSTREAM is not set".to_string()))?;
        let mut rust_routes: Vec<String> = Vec::new();
        for name in settings
            .get("BC_RUST_ROUTES")
            .unwrap_or_default()
            .split(',')
        {
            let name = name.trim().to_ascii_lowercase();
            if !name.is_empty() && !rust_routes.contains(&name) {
                rust_routes.push(name);
            }
        }
        Ok(EdgeConfig {
            python_upstream: check_upstream(&upstream)?,
            rust_routes,
            connect_timeout: seconds(
                settings,
                "BC_PYTHON_UPSTREAM_CONNECT_TIMEOUT_SECS",
                DEFAULT_CONNECT_TIMEOUT_SECS,
            )?,
            idle_timeout: seconds(
                settings,
                "BC_PYTHON_UPSTREAM_TIMEOUT_SECS",
                DEFAULT_IDLE_TIMEOUT_SECS,
            )?,
            served_by_header: settings.flag("BC_SERVED_BY_HEADER")?.unwrap_or(false),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tests::settings;

    fn edge(pairs: &[(&str, &str)]) -> Result<EdgeConfig, ConfigError> {
        let mut all = vec![("BC_PYTHON_UPSTREAM", "http://backend:8000")];
        all.extend_from_slice(pairs);
        EdgeConfig::from_settings(&settings(&all))
    }

    #[test]
    fn the_upstream_is_required() {
        let err = EdgeConfig::from_settings(&settings(&[])).unwrap_err();
        assert!(err.0.contains("BC_PYTHON_UPSTREAM"));
    }

    #[test]
    fn only_a_plain_host_and_port_is_an_upstream_and_the_error_never_echoes_it() {
        assert_eq!(edge(&[]).unwrap().python_upstream, "http://backend:8000");
        let trailing =
            EdgeConfig::from_settings(&settings(&[("BC_PYTHON_UPSTREAM", "http://b:1/")]));
        assert_eq!(trailing.unwrap().python_upstream, "http://b:1");
        for bad in [
            "https://backend:8000",
            "backend:8000",
            "http://user:secret@backend:8000",
            "http://backend:8000/api",
            "http://backend:port",
            "http://",
            "http://:8000",
        ] {
            let err =
                EdgeConfig::from_settings(&settings(&[("BC_PYTHON_UPSTREAM", bad)])).unwrap_err();
            assert!(err.0.starts_with("BC_PYTHON_UPSTREAM"), "{bad}: {err}");
            assert!(
                !err.0.contains("secret") && !err.0.contains("backend:"),
                "{bad}: {err}"
            );
        }
    }

    #[test]
    fn the_route_switch_defaults_to_nothing_and_is_tidied() {
        assert_eq!(edge(&[]).unwrap().rust_routes, Vec::<String>::new());
        let on = edge(&[("BC_RUST_ROUTES", " Permissions, ,permissions,Health ")]).unwrap();
        assert_eq!(on.rust_routes, vec!["permissions", "health"]);
    }

    #[test]
    fn timeouts_have_defaults_and_bounds() {
        let cfg = edge(&[]).unwrap();
        assert_eq!(cfg.connect_timeout, Duration::from_secs(5));
        assert_eq!(cfg.idle_timeout, Duration::from_secs(120));
        assert!(edge(&[("BC_PYTHON_UPSTREAM_TIMEOUT_SECS", "0")]).is_err());
        assert!(edge(&[("BC_PYTHON_UPSTREAM_TIMEOUT_SECS", "soon")]).is_err());
        assert_eq!(
            edge(&[("BC_PYTHON_UPSTREAM_TIMEOUT_SECS", "30")])
                .unwrap()
                .idle_timeout,
            Duration::from_secs(30)
        );
    }
}
