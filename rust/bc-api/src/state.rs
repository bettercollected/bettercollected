//! What every handler shares.

use bc_config::Config;
use bc_http::client_ip::ClientIpRules;
use bc_http::cors::Origins;
use sqlx::PgPool;

use crate::proxy::Proxy;
use crate::store;

#[derive(Debug)]
pub struct AppState {
    pub cfg: Config,
    pub pool: PgPool,
    pub origins: Origins,
    pub client_ip: ClientIpRules,
    pub proxy: Proxy,
}

impl AppState {
    pub fn new(cfg: Config, pool: PgPool) -> AppState {
        let proxy = Proxy::new(
            &cfg.edge.python_upstream,
            cfg.edge.connect_timeout,
            cfg.edge.idle_timeout,
            cfg.edge.served_by_header,
        );
        let client_ip = ClientIpRules::new(
            &cfg.network.trusted_proxies,
            cfg.network.trust_cloudflare,
            &cfg.network.cloudflare_ips,
        );
        AppState {
            cfg,
            pool,
            origins: Origins::default(),
            client_ip,
            proxy,
        }
    }

    /// The origins CORS allows: the cached list, refreshed from the database
    /// once per minute; the stale list when the refresh fails.
    pub async fn allowed_origins(&self) -> Vec<String> {
        if let Some(list) = self.origins.fresh() {
            return list;
        }
        match store::origins::list(&self.pool).await {
            Ok(list) => {
                self.origins.store(list.clone());
                list
            }
            Err(error) => {
                tracing::error!("allowed origins not read: {error}");
                self.origins.stale()
            }
        }
    }
}
