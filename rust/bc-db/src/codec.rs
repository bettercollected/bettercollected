//! A typed document to and from a row (`common/records/codec.py`).
//!
//! The write protocol, as the Python backend does it:
//!
//! 1. a record without an id gets a new one (`ensure_id`);
//! 2. its `doc` is the document encoded as BSON Extended JSON, relaxed: ids as
//!    `{"$oid": ...}`, binary as `{"$binary": ...}`, a datetime as an ISO string
//!    where the table has `bson_encoders` (all tables of `app` but a few) and
//!    as `{"$date": ...}` where it has none, every `None` kept as `null`, every
//!    field of the model present (defaults written out), fields the model does
//!    not know not written;
//! 3. `created_at` / `updated_at` columns are the document's own, read as UTC
//!    (a naive value is taken as UTC); when the document has none, the clock's
//!    now;
//! 4. `_bc_source` is `app`; `_bc_checksum` is `checksum(doc)`
//!    (`crate::canonical`);
//! 5. the spine columns are `GENERATED ALWAYS` by the database from `doc`:
//!    never written.
//!
//! A record type here is a serde struct whose serialisation is step 2: its id
//! field is a [`RecordId`] (`$oid`), a datetime field a [`Stamp`] or
//! [`BsonDate`], an opaque nested part a `serde_json::Value` already in
//! document form.
//!
//! [`BsonDate`]: crate::stamp::BsonDate
//! [`Stamp`]: crate::stamp::Stamp

use chrono::{DateTime, Utc};
use serde::Serialize;
use serde::de::DeserializeOwned;
use serde_json::Value;

use crate::canonical;
use crate::error::DbError;
use crate::id::RecordId;

/// `_bc_source` of a row the application writes.
pub const SOURCE_APP: &str = "app";

/// A document class stored in a table of schema `app`.
pub trait Record: Serialize + DeserializeOwned + Send + Sync + Sized + Unpin {
    /// The table (a trusted constant: it is written into statements).
    const TABLE: &'static str;
    /// The collection name a deletion tombstone records (`__mongo_collection__`
    /// or the table name).
    const COLLECTION: &'static str = Self::TABLE;

    fn id(&self) -> Option<RecordId>;
    fn set_id(&mut self, id: RecordId);
    fn created_at(&self) -> Option<DateTime<Utc>>;
    fn updated_at(&self) -> Option<DateTime<Utc>>;
    /// `Record.__init__`: a missing `created_at` / `updated_at` is stamped with
    /// `now` (on a new record and on one read from a row without them).
    fn stamp_missing(&mut self, now: DateTime<Utc>);
    /// `Record.touch`: what a save does before storing.
    fn touch(&mut self, now: DateTime<Utc>);
}

/// Implements the base accessors of [`Record`] for a struct with the fields
/// `id: Option<RecordId>` (renamed `_id`), `created_at` and `updated_at`
/// (`Option<$moment>`).
#[macro_export]
macro_rules! impl_record {
    ($ty:ty, $table:literal, $moment:ty) => {
        impl $crate::codec::Record for $ty {
            const TABLE: &'static str = $table;
            fn id(&self) -> Option<$crate::id::RecordId> {
                self.id
            }
            fn set_id(&mut self, id: $crate::id::RecordId) {
                self.id = Some(id);
            }
            fn created_at(&self) -> Option<::chrono::DateTime<::chrono::Utc>> {
                self.created_at.as_ref().map($crate::stamp::Moment::to_utc)
            }
            fn updated_at(&self) -> Option<::chrono::DateTime<::chrono::Utc>> {
                self.updated_at.as_ref().map($crate::stamp::Moment::to_utc)
            }
            fn stamp_missing(&mut self, now: ::chrono::DateTime<::chrono::Utc>) {
                if self.created_at.is_none() {
                    self.created_at = Some(<$moment as $crate::stamp::Moment>::from_utc(now));
                }
                if self.updated_at.is_none() {
                    self.updated_at = Some(<$moment as $crate::stamp::Moment>::from_utc(now));
                }
            }
            fn touch(&mut self, now: ::chrono::DateTime<::chrono::Utc>) {
                self.updated_at = Some(<$moment as $crate::stamp::Moment>::from_utc(now));
            }
        }
    };
}

/// The columns an upsert writes.
#[derive(Debug, Clone, PartialEq)]
pub struct RowValues {
    pub id: String,
    pub doc: Value,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub source: &'static str,
    pub checksum: String,
}

/// The `doc` of a record (step 2). Pure: mints nothing. A non-finite float
/// field would become `null` here where Python refuses it: no record holds one.
pub fn encode<T: Record>(record: &T) -> Result<Value, DbError> {
    serde_json::to_value(record).map_err(|e| DbError::Encode(e.to_string()))
}

/// A row's `doc` as the record. Like Python, a document without timestamps is
/// stamped with `now`.
pub fn decode<T: Record>(doc: Value, now: DateTime<Utc>) -> Result<T, DbError> {
    let id = doc
        .get("_id")
        .and_then(|v| crate::value::id_text(Some(v)))
        .unwrap_or_default();
    let mut record: T =
        serde_json::from_value(doc).map_err(|e| DbError::decode(T::TABLE, &id, &e))?;
    record.stamp_missing(now);
    Ok(record)
}

/// Steps 1 to 4. Mints the id when the record has none.
pub fn row_values<T: Record>(record: &mut T, now: DateTime<Utc>) -> Result<RowValues, DbError> {
    if record.id().is_none() {
        let seconds = u32::try_from(now.timestamp().max(0)).unwrap_or(u32::MAX);
        record.set_id(RecordId::mint(seconds));
    }
    record.stamp_missing(now);
    let doc = encode(record)?;
    let id = record.id().map(|i| i.to_string()).unwrap_or_default();
    Ok(RowValues {
        id,
        created_at: record.created_at().unwrap_or(now),
        updated_at: record.updated_at().unwrap_or(now),
        source: SOURCE_APP,
        checksum: canonical::checksum(&doc)?,
        doc,
    })
}
