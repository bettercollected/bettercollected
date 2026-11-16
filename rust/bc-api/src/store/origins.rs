//! `app.allowed_origins` (`AllowedOriginsRepository`).

use sqlx::{PgPool, Row};

/// `AllowedOriginsRepository.list_origins`, in id order.
pub async fn list(pool: &PgPool) -> Result<Vec<String>, sqlx::Error> {
    let rows = sqlx::query("SELECT origin FROM app.allowed_origins ORDER BY id")
        .fetch_all(pool)
        .await?;
    Ok(rows
        .into_iter()
        .filter_map(|r| r.try_get::<Option<String>, _>("origin").ok().flatten())
        .collect())
}
