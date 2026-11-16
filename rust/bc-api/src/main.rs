use std::net::SocketAddr;

use bc_api::{app, groups, state::AppState};
use bc_config::Config;

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
        Err(error) => fail(&format!("configuration: {error}")),
    };
    let unknown = app::unknown_groups(&cfg.edge.rust_routes);
    if !unknown.is_empty() {
        fail(&format!(
            "BC_RUST_ROUTES names groups that do not exist: {} (known: {})",
            unknown.join(", "),
            groups::names().join(", ")
        ));
    }
    // the error can quote the connection string: name nothing
    let Ok(pool) = bc_db::connect(cfg.database_url.expose(), cfg.pool_max).await else {
        fail("Postgres is not reachable with DATABASE_URL")
    };
    if let Err(error) = bc_db::check_schema(&pool).await {
        fail(&error);
    }
    let bind = cfg.bind.clone();
    tracing::info!(
        "serving groups [{}]; everything else goes to the Python backend",
        cfg.edge.rust_routes.join(", ")
    );
    let router = app::router(AppState::new(cfg, pool));
    let listener = match tokio::net::TcpListener::bind(&bind).await {
        Ok(l) => l,
        Err(error) => fail(&format!("cannot listen on {bind}: {error}")),
    };
    tracing::info!("listening on {bind}");
    let served = axum::serve(
        listener,
        router.into_make_service_with_connect_info::<SocketAddr>(),
    )
    .with_graceful_shutdown(shutdown_signal())
    .await;
    if let Err(error) = served {
        fail(&format!("server stopped: {error}"));
    }
}

fn fail(message: &str) -> ! {
    tracing::error!("{message}");
    std::process::exit(1);
}

/// Ctrl-C, or SIGTERM (what `docker stop` sends).
async fn shutdown_signal() {
    let ctrl_c = async {
        let _ = tokio::signal::ctrl_c().await;
    };
    #[cfg(unix)]
    let terminate = async {
        match tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()) {
            Ok(mut signal) => {
                signal.recv().await;
            }
            Err(_) => std::future::pending::<()>().await,
        }
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();
    tokio::select! {
        () = ctrl_c => {},
        () = terminate => {},
    }
}
