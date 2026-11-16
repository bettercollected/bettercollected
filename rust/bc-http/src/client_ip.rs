//! The address a request came from, behind trusted proxies only.
//!
//! A port of `common/common/utils/client_ip.py`, rule for rule. The TCP peer is
//! the client unless it is a proxy we were told to trust (default: nobody).
//! Only then are the forwarding headers believed: `X-Forwarded-For` is a list
//! the client starts and each proxy appends to, so it is walked from the
//! right, skipping trusted proxies; the first other address is the hop that
//! reached our edge (never the left-most entry, which the client chooses).
//! When that hop is a Cloudflare edge, the client is `CF-Connecting-IP`.
//! Neither header is read for a request whose peer is not a trusted proxy.
//! Every address is parsed strictly; anything unparseable is untrustworthy.

use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};
use std::str::FromStr;

use ipnet::IpNet;

/// Entries of `X-Forwarded-For` looked at, from the right; a longer chain is
/// cut there (its leftmost entries are the client's to choose anyway).
pub const MAX_FORWARDED_HOPS: usize = 16;
/// Longest header value looked at.
pub const MAX_HEADER_LENGTH: usize = 4096;

/// Cloudflare's published edge ranges, as of 2026-10-06 (the same list as
/// `CLOUDFLARE_IPS` in the Python module). `API_CLOUDFLARE_IPS` replaces them.
pub const CLOUDFLARE_IPS: &str = "173.245.48.0/20,103.21.244.0/22,103.22.200.0/22,103.31.4.0/22,\
141.101.64.0/18,108.162.192.0/18,190.93.240.0/20,188.114.96.0/20,197.234.240.0/22,198.41.128.0/17,\
162.158.0.0/15,104.16.0.0/13,104.24.0.0/14,172.64.0.0/13,131.0.72.0/22,2400:cb00::/32,\
2606:4700::/32,2803:f800::/32,2405:b500::/32,2405:8100::/32,2a06:98c0::/29,2c0f:f248::/32";

/// `parse_networks`: comma-separated addresses or CIDRs; invalid entries are
/// ignored (a typo narrows trust, it never widens it).
pub fn parse_networks(spec: &str) -> Vec<IpNet> {
    spec.split(',')
        .filter_map(|part| {
            let part = part.trim();
            if part.is_empty() || part.contains('%') {
                return None;
            }
            let net = match part.parse::<IpNet>() {
                Ok(net) => net,
                Err(_) => IpNet::from(part.parse::<IpAddr>().ok()?),
            };
            Some(net.trunc())
        })
        .collect()
}

/// A bare address, `v4:port`, `[v6]` or `[v6]:port`; `None` for anything
/// else. IPv4-mapped IPv6 addresses become IPv4.
pub fn parse_address(value: &str) -> Option<IpAddr> {
    let value = value.trim();
    if value.is_empty() || value.len() > 64 || value.contains('%') {
        return None;
    }
    let bare = if let Some(inner) = value.strip_prefix('[') {
        let end = inner.find(']')?;
        let rest = &inner[end + 1..];
        let port_ok = rest.is_empty()
            || (rest.starts_with(':')
                && rest.len() > 1
                && rest[1..].bytes().all(|b| b.is_ascii_digit()));
        if !port_ok {
            return None;
        }
        &inner[..end]
    } else if value.matches(':').count() == 1 {
        let (host, port) = value.split_once(':')?;
        if port.is_empty() || !port.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        host
    } else {
        value
    };
    let address = IpAddr::from_str(bare).ok()?;
    Some(match address {
        IpAddr::V6(v6) => v6.to_ipv4_mapped().map_or(address, IpAddr::V4),
        v4 @ IpAddr::V4(_) => v4,
    })
}

/// The key a client address is limited or counted under: an IPv4 address as
/// is, an IPv6 address by its /64 (one subscriber's network), "unknown"
/// otherwise.
pub fn rate_limit_key(client: Option<&str>) -> String {
    match client.and_then(parse_address) {
        Some(IpAddr::V4(v4)) => v4.to_string(),
        Some(IpAddr::V6(v6)) => {
            let net = IpNet::new(IpAddr::V6(v6), 64).map(|n| n.trunc());
            net.map_or_else(|_| "unknown".to_string(), |n| n.to_string())
        }
        None => "unknown".to_string(),
    }
}

fn within(address: IpAddr, networks: &[IpNet]) -> bool {
    networks.iter().any(|n| n.contains(&address))
}

/// Python's `ipaddress` `is_private` for IPv4.
fn v4_private(a: Ipv4Addr) -> bool {
    const PRIVATE: &[&str] = &[
        "0.0.0.0/8",
        "10.0.0.0/8",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/29",
        "192.0.0.170/31",
        "192.0.2.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "240.0.0.0/4",
        "255.255.255.255/32",
    ];
    const EXCEPTIONS: &[&str] = &["192.0.0.9/32", "192.0.0.10/32"];
    in_any(IpAddr::V4(a), PRIVATE) && !in_any(IpAddr::V4(a), EXCEPTIONS)
}

/// Python's `ipaddress` `is_private` for IPv6.
fn v6_private(a: Ipv6Addr) -> bool {
    const PRIVATE: &[&str] = &[
        "::1/128",
        "::/128",
        "::ffff:0:0/96",
        "64:ff9b:1::/48",
        "100::/64",
        "2001::/23",
        "2001:db8::/32",
        "2001:10::/28",
        "fc00::/7",
        "fe80::/10",
    ];
    const EXCEPTIONS: &[&str] = &[
        "2001:1::1/128",
        "2001:1::2/128",
        "2001:3::/32",
        "2001:4:112::/48",
        "2001:20::/28",
        "2001:30::/28",
    ];
    in_any(IpAddr::V6(a), PRIVATE) && !in_any(IpAddr::V6(a), EXCEPTIONS)
}

fn in_any(address: IpAddr, nets: &[&str]) -> bool {
    nets.iter()
        .filter_map(|n| n.parse::<IpNet>().ok())
        .any(|n| n.contains(&address))
}

fn is_private_or_loopback(address: IpAddr) -> bool {
    match address {
        IpAddr::V4(a) => v4_private(a) || a.is_loopback(),
        IpAddr::V6(a) => v6_private(a) || a.is_loopback(),
    }
}

/// The proxy trust settings, parsed once.
#[derive(Debug, Clone, Default)]
pub struct ClientIpRules {
    trusted: Vec<IpNet>,
    /// `None`: `CF-Connecting-IP` is never read.
    cloudflare: Option<Vec<IpNet>>,
}

impl ClientIpRules {
    /// `trusted_proxies`: the `TRUSTED_PROXIES` spec; `trust_cloudflare` and
    /// `cloudflare_ips`: `API_TRUST_CLOUDFLARE` and `API_CLOUDFLARE_IPS` (empty:
    /// the built-in ranges).
    pub fn new(trusted_proxies: &str, trust_cloudflare: bool, cloudflare_ips: &str) -> Self {
        let cloudflare = trust_cloudflare.then(|| {
            let spec = if cloudflare_ips.trim().is_empty() {
                CLOUDFLARE_IPS
            } else {
                cloudflare_ips
            };
            parse_networks(spec)
        });
        ClientIpRules {
            trusted: parse_networks(trusted_proxies),
            cloudflare,
        }
    }

    /// The client's address as a string, or `None` when the peer is
    /// unreadable. `peer`: the TCP peer. `forwarded_for`: every
    /// `X-Forwarded-For` header value, in order.
    ///
    /// Behind a proxy that is not listed the answer is the proxy's own
    /// address, shared by every user behind it, not a client: see
    /// [`ClientIpRules::forwarded_by_untrusted_proxy`].
    pub fn resolve(
        &self,
        peer: Option<&str>,
        forwarded_for: &[&str],
        cf_connecting_ip: Option<&str>,
    ) -> Option<String> {
        let mut hop = parse_address(peer?)?;
        if !within(hop, &self.trusted) {
            return Some(hop.to_string()); // not a proxy of ours: its headers are its own words
        }
        let mut edge: Option<IpAddr> = None; // the first hop that isn't our proxy
        let mut hops: Vec<&str> = Vec::new();
        for header in forwarded_for {
            if !header.is_empty() && header.len() <= MAX_HEADER_LENGTH {
                hops.extend(header.split(','));
            }
        }
        let start = hops.len().saturating_sub(MAX_FORWARDED_HOPS);
        for raw in hops[start..].iter().rev() {
            // garbage in the chain: nothing left of it can be believed
            let Some(address) = parse_address(raw) else {
                break;
            };
            if !within(address, &self.trusted) {
                edge = Some(address);
                break;
            }
            hop = address;
        }
        let cloudflare: &[IpNet] = self.cloudflare.as_deref().unwrap_or(&[]);
        if edge.is_none() && within(hop, cloudflare) {
            edge = Some(hop); // a Cloudflare edge we trust connecting to us directly
        }
        // every readable hop was a trusted proxy: the last we could read is
        // as close to the client as we get
        let Some(edge) = edge else {
            return Some(hop.to_string());
        };
        if within(edge, cloudflare)
            && let Some(connecting) = cf_connecting_ip
            && connecting.len() <= MAX_HEADER_LENGTH
            && let Some(address) = parse_address(connecting)
        {
            return Some(address.to_string());
        }
        Some(edge.to_string())
    }

    /// True when the peer is a private or loopback address (a proxy on our own
    /// network, not a client on the internet) that sends forwarding headers
    /// but is not trusted: the address `resolve` returns for such a request is
    /// the proxy's, the same for every user behind it. A per-client budget
    /// must not be counted under it.
    pub fn forwarded_by_untrusted_proxy(
        &self,
        peer: Option<&str>,
        forwarded_for: &[&str],
        cf_connecting_ip: Option<&str>,
    ) -> bool {
        let Some(hop) = peer.and_then(parse_address) else {
            return false;
        };
        if !is_private_or_loopback(hop) {
            return false;
        }
        let sent = forwarded_for.iter().any(|v| !v.trim().is_empty())
            || cf_connecting_ip.is_some_and(|v| !v.trim().is_empty());
        sent && !within(hop, &self.trusted)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rules(trusted: &str) -> ClientIpRules {
        ClientIpRules::new(trusted, true, "")
    }

    #[test]
    fn nobody_is_trusted_by_default_so_the_peer_is_the_client() {
        let r = rules("");
        assert_eq!(
            r.resolve(Some("203.0.113.9"), &["1.2.3.4"], Some("5.6.7.8"))
                .as_deref(),
            Some("203.0.113.9")
        );
        assert_eq!(r.resolve(None, &[], None), None);
        assert_eq!(r.resolve(Some("garbage"), &["1.2.3.4"], None), None);
    }

    #[test]
    fn the_chain_is_walked_from_the_right_never_the_left() {
        let r = rules("10.0.0.0/8");
        // client-chosen left entry is never believed
        assert_eq!(
            r.resolve(Some("10.0.0.1"), &["6.6.6.6, 198.51.100.7, 10.0.0.2"], None)
                .as_deref(),
            Some("198.51.100.7")
        );
        // two headers count as one list
        assert_eq!(
            r.resolve(
                Some("10.0.0.1"),
                &["6.6.6.6", "198.51.100.7, 10.0.0.2"],
                None
            )
            .as_deref(),
            Some("198.51.100.7")
        );
        // all hops trusted: the last readable one
        assert_eq!(
            r.resolve(Some("10.0.0.1"), &["10.0.0.2, 10.0.0.3"], None)
                .as_deref(),
            Some("10.0.0.2")
        );
        // garbage stops the walk: the hop before it stands
        assert_eq!(
            r.resolve(Some("10.0.0.1"), &["1.1.1.1, nope, 10.0.0.2"], None)
                .as_deref(),
            Some("10.0.0.2")
        );
        // no header: the proxy itself
        assert_eq!(
            r.resolve(Some("10.0.0.1"), &[], None).as_deref(),
            Some("10.0.0.1")
        );
    }

    #[test]
    fn an_untrusted_peer_cannot_vouch_for_a_client() {
        let r = rules("10.0.0.0/8");
        assert_eq!(
            r.resolve(Some("192.0.2.1"), &["1.2.3.4"], Some("5.6.7.8"))
                .as_deref(),
            Some("192.0.2.1")
        );
    }

    #[test]
    fn only_the_last_sixteen_hops_are_looked_at() {
        let r = rules("10.0.0.0/8");
        let mut chain = vec!["198.51.100.9".to_string()];
        chain.extend((0..16).map(|i| format!("10.0.0.{i}")));
        let header = chain.join(", ");
        // 16 trusted hops fill the window: the client behind them is out of reach
        assert_eq!(
            r.resolve(Some("10.9.9.9"), &[header.as_str()], None)
                .as_deref(),
            Some("10.0.0.0")
        );
        // an oversize header is ignored altogether
        let long = format!("{}, 1.1.1.1", "9".repeat(MAX_HEADER_LENGTH));
        assert_eq!(
            r.resolve(Some("10.0.0.1"), &[long.as_str()], None)
                .as_deref(),
            Some("10.0.0.1")
        );
    }

    #[test]
    fn cloudflare_names_the_client_only_behind_a_trusted_proxy() {
        let r = rules("10.0.0.0/8");
        let via = r.resolve(
            Some("10.0.0.1"),
            &["203.0.113.50, 104.16.0.5"],
            Some("198.51.100.77"),
        );
        assert_eq!(via.as_deref(), Some("198.51.100.77"));
        // an unparseable CF header falls back to the edge itself
        let via = r.resolve(Some("10.0.0.1"), &["104.16.0.5"], Some("junk"));
        assert_eq!(via.as_deref(), Some("104.16.0.5"));
        // not from a Cloudflare range: CF-Connecting-IP is a client's own word
        let via = r.resolve(Some("10.0.0.1"), &["203.0.113.50"], Some("198.51.100.77"));
        assert_eq!(via.as_deref(), Some("203.0.113.50"));
        // switched off
        let off = ClientIpRules::new("10.0.0.0/8", false, "");
        let via = off.resolve(Some("10.0.0.1"), &["104.16.0.5"], Some("198.51.100.77"));
        assert_eq!(via.as_deref(), Some("104.16.0.5"));
    }

    #[test]
    fn addresses_parse_strictly() {
        assert_eq!(parse_address("1.2.3.4:8080"), "1.2.3.4".parse().ok());
        assert_eq!(
            parse_address("[2001:db8::1]:443"),
            "2001:db8::1".parse().ok()
        );
        assert_eq!(parse_address("[::ffff:1.2.3.4]"), "1.2.3.4".parse().ok());
        assert_eq!(parse_address("::ffff:1.2.3.4"), "1.2.3.4".parse().ok());
        for bad in [
            "",
            "01.2.3.4",
            "1.2.3",
            "1.2.3.4:x",
            "[::1",
            "[::1]x",
            "fe80::1%eth0",
            "1.2.3.4:",
            &"1".repeat(65),
        ] {
            assert_eq!(parse_address(bad), None, "{bad:?}");
        }
    }

    #[test]
    fn a_typo_in_the_trusted_list_narrows_trust() {
        let nets = parse_networks(
            "10.0.0.0/8, nonsense, 10.0.0.0/99, 192.0.2.5, fe80::1%x, 2001:db8::/32",
        );
        assert_eq!(nets.len(), 3);
        // host bits are masked, like ip_network(strict=False)
        assert_eq!(parse_networks("10.1.2.3/8")[0].to_string(), "10.0.0.0/8");
    }

    #[test]
    fn rate_limit_keys_group_an_ipv6_subscriber() {
        assert_eq!(rate_limit_key(Some("1.2.3.4")), "1.2.3.4");
        assert_eq!(
            rate_limit_key(Some("2001:db8:1:2:3:4:5:6")),
            "2001:db8:1:2::/64"
        );
        assert_eq!(
            rate_limit_key(Some("2001:db8:1:2:ffff::1")),
            "2001:db8:1:2::/64"
        );
        assert_eq!(rate_limit_key(Some("nope")), "unknown");
        assert_eq!(rate_limit_key(None), "unknown");
    }

    #[test]
    fn a_private_proxy_that_is_not_listed_is_named() {
        let r = rules("10.0.0.0/8");
        assert!(r.forwarded_by_untrusted_proxy(Some("172.16.0.1"), &["1.2.3.4"], None));
        assert!(r.forwarded_by_untrusted_proxy(Some("127.0.0.1"), &[], Some("1.2.3.4")));
        assert!(!r.forwarded_by_untrusted_proxy(Some("10.0.0.1"), &["1.2.3.4"], None));
        assert!(!r.forwarded_by_untrusted_proxy(Some("172.16.0.1"), &[], None));
        assert!(!r.forwarded_by_untrusted_proxy(Some("8.8.8.8"), &["1.2.3.4"], None));
        assert!(!r.forwarded_by_untrusted_proxy(None, &["1.2.3.4"], None));
    }

    #[test]
    fn private_means_what_pythons_ipaddress_means() {
        for private in [
            "10.1.1.1",
            "172.31.0.1",
            "192.168.0.1",
            "169.254.1.1",
            "100.64.0.1",
        ] {
            let a: IpAddr = private.parse().unwrap();
            // 100.64/10 (shared address space) is NOT private in Python
            assert_eq!(
                is_private_or_loopback(a),
                private != "100.64.0.1",
                "{private}"
            );
        }
        assert!(is_private_or_loopback("fd00::1".parse().unwrap()));
        assert!(is_private_or_loopback("::1".parse().unwrap()));
        assert!(!is_private_or_loopback("2606:4700::1".parse().unwrap()));
        assert!(!is_private_or_loopback("8.8.8.8".parse().unwrap()));
    }
}
