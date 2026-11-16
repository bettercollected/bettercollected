use std::sync::Arc;

use bc_api::{config::Config, cors::Origins, db, routes};

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    let cfg = match Config::from_env() {
        Ok(cfg) => cfg,
        Err(error) => {
            tracing::error!("configuration: {}", error);
            std::process::exit(1);
        }
    };
    let pool = match db::connect(&cfg.database_url, cfg.pool_max).await {
        Ok(pool) => pool,
        Err(_) => {
            // the error can quote the connection string: name nothing
            tracing::error!("Postgres is not reachable with DATABASE_URL");
            std::process::exit(1);
        }
    };
    if let Err(error) = db::check_schema(&pool).await {
        tracing::error!("{}", error);
        std::process::exit(1);
    }
    let bind = cfg.bind.clone();
    let state = Arc::new(routes::AppState {
        cfg,
        pool,
        origins: Origins::default(),
    });
    let app = routes::router(state);
    let listener = match tokio::net::TcpListener::bind(&bind).await {
        Ok(l) => l,
        Err(error) => {
            tracing::error!("cannot listen on {}: {}", bind, error);
            std::process::exit(1);
        }
    };
    tracing::info!("listening on {}", bind);
    let shutdown = async {
        let _ = tokio::signal::ctrl_c().await;
    };
    if let Err(error) = axum::serve(listener, app)
        .with_graceful_shutdown(shutdown)
        .await
    {
        tracing::error!("server stopped: {}", error);
        std::process::exit(1);
    }
}
