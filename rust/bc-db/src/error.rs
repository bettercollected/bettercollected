//! What the data layer reports. A message never carries a stored value: a
//! decode failure names the table, the id and the kind of mismatch only.

use std::fmt;

/// Postgres SQLSTATEs the callers act on.
pub const LOCK_NOT_AVAILABLE: &str = "55P03";
pub const UNIQUE_VIOLATION: &str = "23505";
pub const DEADLOCK: &str = "40P01";
pub const SERIALIZATION_FAILURE: &str = "40001";
pub const QUERY_CANCELED: &str = "57014";

#[derive(Debug)]
pub enum DbError {
    /// Any other database error. Its text can quote a statement's parameters:
    /// do not show it to a client.
    Sql(sqlx::Error),
    /// A lock wait ran past `lock_timeout` (SQLSTATE 55P03): another change to
    /// the record is in progress. Python answers 409 `{"code": "busy"}`.
    Busy,
    /// A unique index refused the write (23505).
    Conflict,
    /// A deadlock or serialisation failure: the whole transaction may be retried.
    Retry,
    /// The statement ran past `statement_timeout` (57014).
    Timeout,
    /// A stored document does not read as the record: `reason` is the
    /// mismatch without the value.
    Decode {
        table: &'static str,
        id: String,
        reason: String,
    },
    /// A value that cannot be written (a non-finite number, a bad column name).
    Encode(String),
    /// The record was expected and is not there.
    NotFound,
}

impl DbError {
    pub fn decode(table: &'static str, id: &str, source: &serde_json::Error) -> Self {
        DbError::Decode {
            table,
            id: id.to_string(),
            reason: scrub(&source.to_string()),
        }
    }
}

/// Keeps the part of a serde message that is about the shape, never the value:
/// the "missing field" text (a field name from our code) and the "expected
/// ..." tail of an "invalid type" message.
fn scrub(message: &str) -> String {
    if message.starts_with("missing field ") {
        return message
            .split(" at line")
            .next()
            .unwrap_or(message)
            .to_string();
    }
    match message.rsplit_once(", expected ") {
        Some((_, tail)) => format!("expected {}", tail.split(" at line").next().unwrap_or(tail)),
        None => "invalid value".to_string(),
    }
}

impl From<sqlx::Error> for DbError {
    fn from(error: sqlx::Error) -> Self {
        let code = error
            .as_database_error()
            .and_then(sqlx::error::DatabaseError::code)
            .map(|c| c.to_string());
        match code.as_deref() {
            Some(LOCK_NOT_AVAILABLE) => DbError::Busy,
            Some(UNIQUE_VIOLATION) => DbError::Conflict,
            Some(DEADLOCK | SERIALIZATION_FAILURE) => DbError::Retry,
            Some(QUERY_CANCELED) => DbError::Timeout,
            _ => DbError::Sql(error),
        }
    }
}

impl From<crate::canonical::NotCanonical> for DbError {
    fn from(error: crate::canonical::NotCanonical) -> Self {
        DbError::Encode(error.to_string())
    }
}

impl fmt::Display for DbError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DbError::Sql(_) => f.write_str("database error"),
            DbError::Busy => f.write_str("another change to this record is in progress"),
            DbError::Conflict => f.write_str("a unique constraint refused the write"),
            DbError::Retry => f.write_str("the transaction lost a race and may be retried"),
            DbError::Timeout => f.write_str("the statement ran past its timeout"),
            DbError::Decode { table, id, reason } => {
                write!(f, "document {id} of {table} does not read: {reason}")
            }
            DbError::Encode(why) => write!(f, "cannot write the document: {why}"),
            DbError::NotFound => f.write_str("record not found"),
        }
    }
}

impl std::error::Error for DbError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            DbError::Sql(e) => Some(e),
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_decode_reason_never_holds_the_value() {
        assert_eq!(
            scrub("missing field `workspace_name`"),
            "missing field `workspace_name`"
        );
        assert_eq!(
            scrub("invalid type: string \"a@b.example\", expected a boolean"),
            "expected a boolean"
        );
        assert_eq!(
            scrub("unknown variant `secret`, expected one of `a`, `b`"),
            "expected one of `a`, `b`"
        );
        assert_eq!(scrub("something with a@b.example"), "invalid value");
    }
}
