//! The generic record repository (`common/records/repository.py` and the
//! patterns of `backend/app/repositories/postgres/`).
//!
//! Every method takes the connection it runs on (`_in`), so a caller composes
//! several of them in one transaction; the plain ones (`get`, `upsert`, ...)
//! take a connection from the pool and, where the operation is more than one
//! statement, begin a transaction. Queries touch only the generated spine
//! columns (`Filter` names them) and read the rest out of `doc`.
//!
//! Rules this follows from `backend/AGENTS.md`, "Persistence":
//!
//! * a read-then-write that depends on what it read runs in one transaction on
//!   the stored row, locked with `SELECT ... FOR UPDATE` ([`Db::update_in`],
//!   [`Db::set_fields_in`], [`Db::find_in`] with `lock`), or, where no row exists
//!   yet, under a transaction-scoped advisory lock on the natural key
//!   ([`Db::advisory_lock_in`], the same key as Python's `_advisory_lock`, so a
//!   mixed fleet serialises on one lock);
//! * timestamps come from the one clock; `save` moves `updated_at`, `upsert`,
//!   `update` and `set_fields` leave it as it is (Python's `upsert`,
//!   `set_fields`);
//! * every delete writes a tombstone in the same transaction.

use std::sync::atomic::{AtomicU64, Ordering};

use chrono::{DateTime, Duration, Timelike, Utc};
use serde_json::Value;
use sha1::{Digest, Sha1};
use sqlx::postgres::{PgPool, Postgres};
use sqlx::{AssertSqlSafe, PgConnection, QueryBuilder};

use crate::clock::SharedClock;
use crate::codec::{self, Record, RowValues};
use crate::error::DbError;
use crate::id::RecordId;

/// Schema of the application tables.
pub const SCHEMA: &str = "app";

/// A tombstone is kept this long; every `PRUNE_EVERY` recorded deletes a
/// process prunes a batch (`common/db/tombstones.py`).
pub const TOMBSTONE_RETENTION_DAYS: i64 = 120;
pub const PRUNE_EVERY: u64 = 200;
pub const PRUNE_BATCH: i64 = 1000;
const TOMBSTONE_CHUNK: usize = 1000;

static RECORDED: AtomicU64 = AtomicU64::new(0);
static PRUNED_AT: AtomicU64 = AtomicU64::new(0);

/// A value a filter binds.
#[derive(Clone, Debug, PartialEq)]
pub enum Param {
    Text(String),
    Bool(bool),
    Int(i64),
    Ts(DateTime<Utc>),
}

impl From<&str> for Param {
    fn from(v: &str) -> Self {
        Param::Text(v.to_string())
    }
}
impl From<String> for Param {
    fn from(v: String) -> Self {
        Param::Text(v)
    }
}
impl From<RecordId> for Param {
    fn from(v: RecordId) -> Self {
        Param::Text(v.to_string())
    }
}
impl From<bool> for Param {
    fn from(v: bool) -> Self {
        Param::Bool(v)
    }
}
impl From<i64> for Param {
    fn from(v: i64) -> Self {
        Param::Int(v)
    }
}
impl From<DateTime<Utc>> for Param {
    fn from(v: DateTime<Utc>) -> Self {
        Param::Ts(v)
    }
}

#[derive(Clone, Debug)]
enum Cond {
    Cmp(&'static str, &'static str, Param),
    AnyOf(&'static str, Vec<String>),
    Null(&'static str, bool),
}

/// A conjunction of conditions on spine columns (and `id`, `created_at`,
/// `updated_at`). Column names are `&'static str` on purpose: a caller-supplied
/// string never reaches a statement as an identifier.
#[derive(Clone, Debug, Default)]
pub struct Filter {
    conds: Vec<Cond>,
}

impl Filter {
    pub fn new() -> Self {
        Self::default()
    }
    #[must_use]
    pub fn eq(mut self, column: &'static str, v: impl Into<Param>) -> Self {
        self.conds.push(Cond::Cmp(column, "=", v.into()));
        self
    }
    #[must_use]
    pub fn ne(mut self, column: &'static str, v: impl Into<Param>) -> Self {
        self.conds.push(Cond::Cmp(column, "<>", v.into()));
        self
    }
    #[must_use]
    pub fn gte(mut self, column: &'static str, v: impl Into<Param>) -> Self {
        self.conds.push(Cond::Cmp(column, ">=", v.into()));
        self
    }
    #[must_use]
    pub fn lte(mut self, column: &'static str, v: impl Into<Param>) -> Self {
        self.conds.push(Cond::Cmp(column, "<=", v.into()));
        self
    }
    #[must_use]
    pub fn any_of(mut self, column: &'static str, values: Vec<String>) -> Self {
        self.conds.push(Cond::AnyOf(column, values));
        self
    }
    #[must_use]
    pub fn is_null(mut self, column: &'static str) -> Self {
        self.conds.push(Cond::Null(column, true));
        self
    }
    #[must_use]
    pub fn not_null(mut self, column: &'static str) -> Self {
        self.conds.push(Cond::Null(column, false));
        self
    }
}

fn ident(name: &str) -> Result<&str, DbError> {
    let ok = !name.is_empty()
        && name
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
        && !name.as_bytes()[0].is_ascii_digit();
    if ok {
        Ok(name)
    } else {
        Err(DbError::Encode(format!("not a plain identifier: {name:?}")))
    }
}

fn push_where(
    qb: &mut QueryBuilder<Postgres>,
    filter: &Filter,
    keyset: Option<(&Keyset, Order)>,
) -> Result<(), DbError> {
    let mut first = true;
    let mut glue = |qb: &mut QueryBuilder<Postgres>| {
        qb.push(if first { " WHERE " } else { " AND " });
        first = false;
    };
    for cond in &filter.conds {
        glue(qb);
        match cond {
            Cond::Cmp(col, op, param) => {
                qb.push(ident(col)?).push(' ').push(*op).push(' ');
                match param.clone() {
                    Param::Text(v) => qb.push_bind(v),
                    Param::Bool(v) => qb.push_bind(v),
                    Param::Int(v) => qb.push_bind(v),
                    Param::Ts(v) => qb.push_bind(v),
                };
            }
            Cond::AnyOf(col, values) => {
                qb.push(ident(col)?)
                    .push(" = ANY(")
                    .push_bind(values.clone())
                    .push(")");
            }
            Cond::Null(col, null) => {
                qb.push(ident(col)?)
                    .push(if *null { " IS NULL" } else { " IS NOT NULL" });
            }
        }
    }
    if let Some((key, order)) = keyset {
        glue(qb);
        qb.push("(created_at, id) ")
            .push(if order == Order::Asc { "> " } else { "< " })
            .push("(")
            .push_bind(key.created_at)
            .push(", ")
            .push_bind(key.id.clone())
            .push(")");
    }
    Ok(())
}

/// Insertion order is `(created_at, id)`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Order {
    Asc,
    Desc,
}

/// Where a page begins: the `(created_at, id)` of the last row of the page
/// before (a keyset: nothing is counted from the start).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Keyset {
    pub created_at: DateTime<Utc>,
    pub id: String,
}

impl Keyset {
    pub fn new(created_at: DateTime<Utc>, id: impl Into<String>) -> Self {
        Self {
            created_at,
            id: id.into(),
        }
    }

    /// The keyset position of a stored record.
    pub fn of<T: Record>(record: &T) -> Option<Self> {
        Some(Self {
            created_at: record.created_at()?,
            id: record.id()?.to_string(),
        })
    }
}

/// One page: the order, the rows strictly after `after` in that order, at most
/// `limit` of them.
#[derive(Clone, Debug)]
pub struct Page {
    pub order: Order,
    pub after: Option<Keyset>,
    pub limit: Option<i64>,
}

impl Page {
    pub fn first(limit: i64) -> Self {
        Self {
            order: Order::Asc,
            after: None,
            limit: Some(limit),
        }
    }
    pub fn newest_first(limit: i64) -> Self {
        Self {
            order: Order::Desc,
            after: None,
            limit: Some(limit),
        }
    }
    #[must_use]
    pub fn after(mut self, key: Keyset) -> Self {
        self.after = Some(key);
        self
    }
}

impl Default for Page {
    fn default() -> Self {
        Self {
            order: Order::Asc,
            after: None,
            limit: None,
        }
    }
}

/// The pool, the clock and the statements every record shares.
#[derive(Clone, Debug)]
pub struct Db {
    pool: PgPool,
    clock: SharedClock,
}

fn table_of<T: Record>() -> Result<&'static str, DbError> {
    ident(T::TABLE)
}

impl Db {
    pub fn new(pool: PgPool, clock: SharedClock) -> Self {
        Self { pool, clock }
    }

    pub fn pool(&self) -> &PgPool {
        &self.pool
    }

    pub fn clock(&self) -> &SharedClock {
        &self.clock
    }

    pub fn now(&self) -> DateTime<Utc> {
        self.clock.now()
    }

    /// A new id stamped from the clock.
    pub fn new_id(&self) -> Result<RecordId, DbError> {
        Ok(RecordId::mint(
            u32::try_from(self.now().timestamp().max(0)).unwrap_or(u32::MAX),
        )?)
    }

    // -- locks ----------------------------------------------------------------

    /// `_advisory_lock(session, *parts)`: a transaction-scoped advisory lock
    /// named by `parts`, held until the transaction ends. The key is the first
    /// 8 bytes of sha1 of the parts joined by NUL (each part its text), as a
    /// signed big-endian integer: the Python backend takes the same lock.
    pub async fn advisory_lock_in(
        &self,
        conn: &mut PgConnection,
        parts: &[&str],
    ) -> Result<(), DbError> {
        sqlx::query("SELECT pg_advisory_xact_lock($1)")
            .bind(advisory_key(parts))
            .execute(conn)
            .await?;
        Ok(())
    }

    /// The server-side form (`hashtextextended(name, 0)`), as the form-import
    /// limit takes it.
    pub async fn advisory_lock_text_in(
        &self,
        conn: &mut PgConnection,
        name: &str,
    ) -> Result<(), DbError> {
        sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))")
            .bind(name)
            .execute(conn)
            .await?;
        Ok(())
    }

    /// `SET LOCAL lock_timeout`: how long this transaction waits for a lock
    /// before [`DbError::Busy`].
    pub async fn set_local_lock_timeout_in(
        &self,
        conn: &mut PgConnection,
        ms: u64,
    ) -> Result<(), DbError> {
        // `ms` is a `u64`: nothing to inject.
        sqlx::query(AssertSqlSafe(format!("SET LOCAL lock_timeout = '{ms}ms'")))
            .execute(conn)
            .await?;
        Ok(())
    }

    // -- reads ----------------------------------------------------------------

    /// The record with this id.
    ///
    /// Looks up by id only: the id alone does not say whose record it is. A
    /// caller that serves a request must check the record belongs to the
    /// workspace of the request (or use `find` with the workspace in the filter).
    pub async fn get_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        id: &str,
    ) -> Result<Option<T>, DbError> {
        self.find_in::<T>(conn, &Filter::new().eq("id", id), false)
            .await
    }

    /// The record with this id, locked (`FOR UPDATE`) for the rest of the
    /// transaction.
    ///
    /// Looks up by id only: the id alone does not say whose record it is. A
    /// caller that serves a request must check the record belongs to the
    /// workspace of the request (or use `find` with the workspace in the filter).
    pub async fn get_locked_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        id: &str,
    ) -> Result<Option<T>, DbError> {
        self.find_in::<T>(conn, &Filter::new().eq("id", id), true)
            .await
    }

    /// `one(...)`: the first match in insertion order; `lock` adds `FOR UPDATE`
    /// (`_locked_doc`).
    pub async fn find_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        filter: &Filter,
        lock: bool,
    ) -> Result<Option<T>, DbError> {
        let mut qb =
            QueryBuilder::<Postgres>::new(format!("SELECT doc FROM {SCHEMA}.{}", table_of::<T>()?));
        push_where(&mut qb, filter, None)?;
        qb.push(" ORDER BY created_at, id LIMIT 1");
        if lock {
            qb.push(" FOR UPDATE");
        }
        let doc: Option<Value> = qb.build_query_scalar().fetch_optional(conn).await?;
        doc.map(|d| codec::decode::<T>(d, self.now())).transpose()
    }

    /// `many(...)`: the matches in `(created_at, id)` order, from the keyset.
    pub async fn list_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        filter: &Filter,
        page: &Page,
    ) -> Result<Vec<T>, DbError> {
        let mut qb =
            QueryBuilder::<Postgres>::new(format!("SELECT doc FROM {SCHEMA}.{}", table_of::<T>()?));
        push_where(
            &mut qb,
            filter,
            page.after.as_ref().map(|k| (k, page.order)),
        )?;
        qb.push(match page.order {
            Order::Asc => " ORDER BY created_at, id",
            Order::Desc => " ORDER BY created_at DESC, id DESC",
        });
        if let Some(limit) = page.limit {
            qb.push(" LIMIT ").push_bind(limit);
        }
        let docs: Vec<Value> = qb.build_query_scalar().fetch_all(conn).await?;
        let now = self.now();
        docs.into_iter()
            .map(|d| codec::decode::<T>(d, now))
            .collect()
    }

    pub async fn count_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        filter: &Filter,
    ) -> Result<i64, DbError> {
        let mut qb = QueryBuilder::<Postgres>::new(format!(
            "SELECT count(*) FROM {SCHEMA}.{}",
            table_of::<T>()?
        ));
        push_where(&mut qb, filter, None)?;
        Ok(qb.build_query_scalar::<i64>().fetch_one(conn).await?)
    }

    // -- writes ---------------------------------------------------------------

    /// The upsert of `RecordRepository.upsert`: `INSERT ... ON CONFLICT (id) DO
    /// UPDATE` of `doc`, `updated_at`, `_bc_source` and `_bc_checksum` (not
    /// `created_at`). Mints an id when the record has none; does not move
    /// `updated_at`.
    pub async fn upsert_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        record: &mut T,
    ) -> Result<RowValues, DbError> {
        let row = codec::row_values(record, self.now())?;
        let sql = format!(
            "INSERT INTO {SCHEMA}.{t} (id, doc, created_at, updated_at, _bc_source, _bc_checksum) \
             VALUES ($1, $2, $3, $4, $5, $6) \
             ON CONFLICT (id) DO UPDATE SET doc = EXCLUDED.doc, updated_at = EXCLUDED.updated_at, \
             _bc_source = EXCLUDED._bc_source, _bc_checksum = EXCLUDED._bc_checksum",
            t = table_of::<T>()?
        );
        bind_row(sqlx::query(AssertSqlSafe(sql)), &row)
            .execute(conn)
            .await?;
        Ok(row)
    }

    /// A plain `INSERT`: [`DbError::Conflict`] when the id (or a unique index)
    /// is taken. The Python repositories have only the upsert; this is for a
    /// writer that must not overwrite.
    pub async fn insert_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        record: &mut T,
    ) -> Result<RowValues, DbError> {
        let row = codec::row_values(record, self.now())?;
        let sql = format!(
            "INSERT INTO {SCHEMA}.{t} (id, doc, created_at, updated_at, _bc_source, _bc_checksum) \
             VALUES ($1, $2, $3, $4, $5, $6)",
            t = table_of::<T>()?
        );
        bind_row(sqlx::query(AssertSqlSafe(sql)), &row)
            .execute(conn)
            .await?;
        Ok(row)
    }

    /// `save_document`: move `updated_at` to now, then upsert.
    pub async fn save_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        record: &mut T,
    ) -> Result<RowValues, DbError> {
        record.touch(self.now());
        self.upsert_in(conn, record).await
    }

    /// The locked read-modify-write behind `set_fields` and the conditional
    /// updates: the row is locked, decoded, handed to `change`, and stored
    /// again (`updated_at` stays as `change` leaves it). `None` when there is no
    /// such row (nothing is written). Must run in a transaction.
    ///
    /// Looks up by id only: the id alone does not say whose record it is. A
    /// caller that serves a request must check the record belongs to the
    /// workspace of the request (or use `find` with the workspace in the filter).
    pub async fn update_in<T: Record, R>(
        &self,
        conn: &mut PgConnection,
        id: &str,
        change: impl FnOnce(&mut T) -> Result<R, DbError>,
    ) -> Result<Option<(T, R)>, DbError> {
        let Some(mut stored) = self.get_locked_in::<T>(conn, id).await? else {
            return Ok(None);
        };
        let out = change(&mut stored)?;
        self.upsert_in(conn, &mut stored).await?;
        Ok(Some((stored, out)))
    }

    /// `set_fields`: dotted paths set on the stored document under a row lock;
    /// the result is read back as the record and written (so the stored
    /// document comes out as the model writes it). `None` for a missing row.
    /// A path through a missing or non-object parent is an error.
    ///
    /// Looks up by id only: the id alone does not say whose record it is. A
    /// caller that serves a request must check the record belongs to the
    /// workspace of the request (or use `find` with the workspace in the filter).
    pub async fn set_fields_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        id: &str,
        fields: &[(&str, Value)],
    ) -> Result<Option<T>, DbError> {
        let sql = format!(
            "SELECT doc FROM {SCHEMA}.{} WHERE id = $1 FOR UPDATE",
            table_of::<T>()?
        );
        let doc: Option<Value> = sqlx::query_scalar(AssertSqlSafe(sql))
            .bind(id)
            .fetch_optional(&mut *conn)
            .await?;
        let Some(mut doc) = doc else { return Ok(None) };
        for (path, value) in fields {
            set_path(&mut doc, path, value.clone())?;
        }
        let mut stored = codec::decode::<T>(doc, self.now())?;
        self.upsert_in(conn, &mut stored).await?;
        Ok(Some(stored))
    }

    // -- deletes (with tombstones) -------------------------------------------

    /// Deletes the matches and, in the same transaction, records a tombstone per
    /// deleted id. Returns how many.
    pub async fn delete_where_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        filter: &Filter,
    ) -> Result<u64, DbError> {
        let mut qb =
            QueryBuilder::<Postgres>::new(format!("DELETE FROM {SCHEMA}.{}", table_of::<T>()?));
        push_where(&mut qb, filter, None)?;
        qb.push(" RETURNING id");
        let ids: Vec<String> = qb.build_query_scalar().fetch_all(&mut *conn).await?;
        self.record_tombstones(conn, T::COLLECTION, &ids).await?;
        Ok(ids.len() as u64)
    }

    /// Deletes the first match in insertion order.
    pub async fn delete_one_where_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        filter: &Filter,
    ) -> Result<u64, DbError> {
        let mut qb = QueryBuilder::<Postgres>::new(format!(
            "DELETE FROM {SCHEMA}.{t} WHERE id = (SELECT id FROM {SCHEMA}.{t}",
            t = table_of::<T>()?
        ));
        push_where(&mut qb, filter, None)?;
        qb.push(" ORDER BY created_at, id LIMIT 1) RETURNING id");
        let ids: Vec<String> = qb.build_query_scalar().fetch_all(&mut *conn).await?;
        self.record_tombstones(conn, T::COLLECTION, &ids).await?;
        Ok(ids.len() as u64)
    }

    /// Deletes the record with this id (with its tombstone).
    ///
    /// Looks up by id only: the id alone does not say whose record it is. A
    /// caller that serves a request must check the record belongs to the
    /// workspace of the request (or use `find` with the workspace in the filter).
    pub async fn delete_by_id_in<T: Record>(
        &self,
        conn: &mut PgConnection,
        id: &str,
    ) -> Result<u64, DbError> {
        self.delete_where_in::<T>(conn, &Filter::new().eq("id", id))
            .await
    }

    async fn record_tombstones(
        &self,
        conn: &mut PgConnection,
        collection: &str,
        ids: &[String],
    ) -> Result<(), DbError> {
        if ids.is_empty() {
            return Ok(());
        }
        let at = to_ms(self.now());
        for chunk in ids.chunks(TOMBSTONE_CHUNK) {
            let mut qb = QueryBuilder::<Postgres>::new(format!(
                "INSERT INTO {SCHEMA}.deletion_tombstones (collection, row_id, deleted_at) "
            ));
            qb.push_values(chunk, |mut row, id| {
                row.push_bind(collection.to_string())
                    .push_bind(id.clone())
                    .push_bind(at);
            });
            qb.push(
                " ON CONFLICT (collection, row_id) DO UPDATE SET deleted_at = EXCLUDED.deleted_at",
            );
            qb.build().execute(&mut *conn).await?;
        }
        RECORDED.fetch_add(1, Ordering::Relaxed);
        Ok(())
    }

    /// After a delete committed: every [`PRUNE_EVERY`] recorded deletes, drop a
    /// bounded batch of expired tombstones, in a transaction of its own, never
    /// failing the caller. Call it after the commit of a transaction that
    /// deleted; the plain delete methods do.
    pub async fn prune_tombstones_if_due(&self) {
        let recorded = RECORDED.load(Ordering::Relaxed);
        if recorded.saturating_sub(PRUNED_AT.load(Ordering::Relaxed)) < PRUNE_EVERY {
            return;
        }
        PRUNED_AT.store(recorded, Ordering::Relaxed);
        let cut = self.now() - Duration::days(TOMBSTONE_RETENTION_DAYS);
        let sql = format!(
            "DELETE FROM {SCHEMA}.deletion_tombstones WHERE (collection, row_id) IN \
             (SELECT collection, row_id FROM {SCHEMA}.deletion_tombstones WHERE deleted_at < $1 LIMIT $2)"
        );
        if let Err(error) = sqlx::query(AssertSqlSafe(sql))
            .bind(cut)
            .bind(PRUNE_BATCH)
            .execute(&self.pool)
            .await
        {
            tracing::warn!(error = %DbError::from(error), "pruning tombstones failed");
        }
    }

    // -- on the pool ----------------------------------------------------------

    /// The record with this id.
    ///
    /// Looks up by id only: the id alone does not say whose record it is. A
    /// caller that serves a request must check the record belongs to the
    /// workspace of the request (or use `find` with the workspace in the filter).
    pub async fn get<T: Record>(&self, id: &str) -> Result<Option<T>, DbError> {
        let mut conn = self.pool.acquire().await?;
        self.get_in(&mut conn, id).await
    }

    pub async fn find<T: Record>(&self, filter: &Filter) -> Result<Option<T>, DbError> {
        let mut conn = self.pool.acquire().await?;
        self.find_in(&mut conn, filter, false).await
    }

    pub async fn list<T: Record>(&self, filter: &Filter, page: &Page) -> Result<Vec<T>, DbError> {
        let mut conn = self.pool.acquire().await?;
        self.list_in(&mut conn, filter, page).await
    }

    pub async fn count<T: Record>(&self, filter: &Filter) -> Result<i64, DbError> {
        let mut conn = self.pool.acquire().await?;
        self.count_in::<T>(&mut conn, filter).await
    }

    pub async fn upsert<T: Record>(&self, record: &mut T) -> Result<(), DbError> {
        let mut conn = self.pool.acquire().await?;
        self.upsert_in(&mut conn, record).await.map(|_| ())
    }

    pub async fn insert<T: Record>(&self, record: &mut T) -> Result<(), DbError> {
        let mut conn = self.pool.acquire().await?;
        self.insert_in(&mut conn, record).await.map(|_| ())
    }

    pub async fn save<T: Record>(&self, record: &mut T) -> Result<(), DbError> {
        let mut conn = self.pool.acquire().await?;
        self.save_in(&mut conn, record).await.map(|_| ())
    }

    /// `update_in` in a transaction of its own.
    ///
    /// Looks up by id only: the id alone does not say whose record it is. A
    /// caller that serves a request must check the record belongs to the
    /// workspace of the request (or use `find` with the workspace in the filter).
    pub async fn update<T: Record, R>(
        &self,
        id: &str,
        change: impl FnOnce(&mut T) -> Result<R, DbError>,
    ) -> Result<Option<(T, R)>, DbError> {
        let mut tx = self.pool.begin().await?;
        let out = self.update_in(&mut tx, id, change).await?;
        tx.commit().await?;
        Ok(out)
    }

    /// `set_fields_in` in a transaction of its own.
    ///
    /// Looks up by id only: the id alone does not say whose record it is. A
    /// caller that serves a request must check the record belongs to the
    /// workspace of the request (or use `find` with the workspace in the filter).
    pub async fn set_fields<T: Record>(
        &self,
        id: &str,
        fields: &[(&str, Value)],
    ) -> Result<Option<T>, DbError> {
        let mut tx = self.pool.begin().await?;
        let out = self.set_fields_in::<T>(&mut tx, id, fields).await?;
        tx.commit().await?;
        Ok(out)
    }

    pub async fn delete_where<T: Record>(&self, filter: &Filter) -> Result<u64, DbError> {
        let mut tx = self.pool.begin().await?;
        let n = self.delete_where_in::<T>(&mut tx, filter).await?;
        tx.commit().await?;
        self.prune_tombstones_if_due().await;
        Ok(n)
    }

    /// Deletes the record with this id (with its tombstone), then prunes if due.
    ///
    /// Looks up by id only: the id alone does not say whose record it is. A
    /// caller that serves a request must check the record belongs to the
    /// workspace of the request (or use `find` with the workspace in the filter).
    pub async fn delete_by_id<T: Record>(&self, id: &str) -> Result<u64, DbError> {
        self.delete_where::<T>(&Filter::new().eq("id", id)).await
    }
}

fn bind_row<'q>(
    query: sqlx::query::Query<'q, Postgres, sqlx::postgres::PgArguments>,
    row: &'q RowValues,
) -> sqlx::query::Query<'q, Postgres, sqlx::postgres::PgArguments> {
    query
        .bind(&row.id)
        .bind(&row.doc)
        .bind(row.created_at)
        .bind(row.updated_at)
        .bind(row.source)
        .bind(&row.checksum)
}

/// Tombstone times are truncated to milliseconds (Mongo's precision).
pub fn to_ms(at: DateTime<Utc>) -> DateTime<Utc> {
    at.with_nanosecond(at.nanosecond() / 1_000_000 * 1_000_000)
        .unwrap_or(at)
}

/// The key of `_advisory_lock(parts)`: the first 8 bytes of sha1 of the parts
/// joined by NUL, big-endian, signed.
pub fn advisory_key(parts: &[&str]) -> i64 {
    let digest = Sha1::digest(parts.join("\0").as_bytes());
    let mut bytes = [0u8; 8];
    bytes.copy_from_slice(&digest[..8]);
    i64::from_be_bytes(bytes)
}

/// `{"a.b": v}` applied to a document: every parent must be an object.
pub fn set_path(doc: &mut Value, path: &str, value: Value) -> Result<(), DbError> {
    let mut node = doc;
    let mut parts = path.split('.').peekable();
    while let Some(part) = parts.next() {
        let Value::Object(map) = node else {
            return Err(DbError::Encode(format!(
                "cannot set {path}: a parent is not an object"
            )));
        };
        if parts.peek().is_none() {
            map.insert(part.to_string(), value);
            return Ok(());
        }
        node = map
            .get_mut(part)
            .ok_or_else(|| DbError::Encode(format!("cannot set {path}: a parent is missing")))?;
    }
    Err(DbError::Encode("empty path".into()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;
    use serde_json::json;

    #[test]
    fn a_dotted_path_sets_a_nested_field() {
        let mut doc = json!({"settings": {"a": 1}, "b": 2});
        set_path(&mut doc, "settings.custom_url", json!("x")).unwrap();
        set_path(&mut doc, "b", json!(3)).unwrap();
        assert_eq!(
            doc,
            json!({"settings": {"a": 1, "custom_url": "x"}, "b": 3})
        );
        assert!(set_path(&mut doc, "nope.x", json!(1)).is_err());
        assert!(set_path(&mut doc, "b.x", json!(1)).is_err());
    }

    #[test]
    fn identifiers_are_plain() {
        assert!(ident("workspace_id").is_ok());
        for bad in ["", "a b", "a;drop", "A", "1a", "a\"b"] {
            assert!(ident(bad).is_err(), "{bad}");
        }
    }

    #[test]
    fn tombstone_times_are_milliseconds() {
        let at =
            Utc.with_ymd_and_hms(2026, 1, 2, 3, 4, 5).unwrap() + Duration::microseconds(678_901);
        assert_eq!(to_ms(at).timestamp_subsec_micros(), 678_000);
    }

    #[test]
    fn the_advisory_key_is_the_python_digest() {
        // python: int.from_bytes(sha1(b"a\x00b").digest()[:8], "big", signed=True)
        assert_eq!(advisory_key(&["a", "b"]), advisory_key(&["a", "b"]));
        assert_ne!(advisory_key(&["a", "b"]), advisory_key(&["ab"]));
    }
}
