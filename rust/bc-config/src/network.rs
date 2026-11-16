//! Which proxies in front of the service are believed about the client
//! address. Same names and defaults as `backend/config/api_settings.py`.
//! The rules that use them are in `bc-http`'s `client_ip`.

use crate::ConfigError;
use crate::source::Settings;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NetworkConfig {
    /// `TRUSTED_PROXIES` (or `API_TRUSTED_PROXIES`, the original name):
    /// comma-separated addresses or CIDRs. Default: none, so the TCP peer is
    /// the client whatever headers the request carries.
    pub trusted_proxies: String,
    /// `API_TRUST_CLOUDFLARE` (default on): behind a trusted proxy, a
    /// Cloudflare edge's `CF-Connecting-IP` names the client.
    pub trust_cloudflare: bool,
    /// `API_CLOUDFLARE_IPS`: replaces the built-in Cloudflare ranges when set.
    pub cloudflare_ips: String,
}

impl NetworkConfig {
    pub fn from_settings(settings: &Settings) -> Result<NetworkConfig, ConfigError> {
        Ok(NetworkConfig {
            trusted_proxies: settings
                .get_any(&["TRUSTED_PROXIES", "API_TRUSTED_PROXIES"])
                .unwrap_or_default(),
            trust_cloudflare: settings.flag("API_TRUST_CLOUDFLARE")?.unwrap_or(true),
            cloudflare_ips: settings.get("API_CLOUDFLARE_IPS").unwrap_or_default(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tests::settings;

    #[test]
    fn defaults_trust_no_proxy_and_cloudflare_is_on() {
        let net = NetworkConfig::from_settings(&settings(&[])).unwrap();
        assert!(net.trusted_proxies.is_empty() && net.cloudflare_ips.is_empty());
        assert!(net.trust_cloudflare);
    }

    #[test]
    fn the_original_name_works_and_the_new_one_wins() {
        let old = NetworkConfig::from_settings(&settings(&[("API_TRUSTED_PROXIES", "10.0.0.0/8")]))
            .unwrap();
        assert_eq!(old.trusted_proxies, "10.0.0.0/8");
        let both = NetworkConfig::from_settings(&settings(&[
            ("API_TRUSTED_PROXIES", "10.0.0.0/8"),
            ("TRUSTED_PROXIES", "172.16.0.0/12"),
        ]))
        .unwrap();
        assert_eq!(both.trusted_proxies, "172.16.0.0/12");
    }
}
