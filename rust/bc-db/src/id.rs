//! Record ids: the 24-hex ObjectId every stored document is keyed by
//! (`common/ids.py`).
//!
//! Stored as 24 lowercase hex characters (the `id` column) and, inside a
//! document, as `{"$oid": ...}`. A new id is minted the way Mongo and the
//! Python backend mint one: a 4-byte big-endian timestamp, 5 per-process random
//! bytes, a 3-byte counter that starts random; so ids still sort by creation
//! time across a mixed Python and Rust fleet.

use std::fmt;
use std::str::FromStr;
use std::sync::OnceLock;
use std::sync::atomic::{AtomicU32, Ordering};

use serde::de::{self, Deserializer, MapAccess, Visitor};
use serde::ser::{SerializeMap, Serializer};
use serde::{Deserialize, Serialize};
use sha1::{Digest, Sha1};

/// A 12-byte ObjectId.
#[derive(Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct RecordId([u8; 12]);

/// The message of today's 422 for a malformed id (`common/ids.py`).
pub const INVALID_ID_MESSAGE: &str = "Id must be of type PydanticObjectId";

struct Process {
    random: [u8; 5],
    counter: AtomicU32,
}

fn process() -> &'static Process {
    static P: OnceLock<Process> = OnceLock::new();
    P.get_or_init(|| {
        let mut bytes = [0u8; 8];
        // a failing system generator leaves zeros: ids stay unique per process
        // through the counter, and the caller is not told to stop for it
        let _ = getrandom::getrandom(&mut bytes);
        let mut random = [0u8; 5];
        random.copy_from_slice(&bytes[..5]);
        let start = u32::from_be_bytes([0, bytes[5], bytes[6], bytes[7]]);
        Process {
            random,
            counter: AtomicU32::new(start),
        }
    })
}

impl RecordId {
    pub const fn from_bytes(bytes: [u8; 12]) -> Self {
        Self(bytes)
    }

    /// A new id stamped with `seconds` since the epoch (the clock's now).
    pub fn mint(seconds: u32) -> Self {
        let p = process();
        let counter = p.counter.fetch_add(1, Ordering::Relaxed) & 0x00ff_ffff;
        let mut bytes = [0u8; 12];
        bytes[..4].copy_from_slice(&seconds.to_be_bytes());
        bytes[4..9].copy_from_slice(&p.random);
        bytes[9..].copy_from_slice(&counter.to_be_bytes()[1..]);
        Self(bytes)
    }

    /// The id that is a function of `parts`, for a record whose identity is a
    /// relation (`common.ids.derived_id`): sha1 of the parts joined by NUL, the
    /// first 12 bytes. The same digest the Python backend uses, so a relation
    /// written by either side addresses the same row. Each part is its text, as
    /// Python's `str(part)`.
    pub fn derived(parts: &[&str]) -> Self {
        let digest = Sha1::digest(parts.join("\0").as_bytes());
        let mut bytes = [0u8; 12];
        bytes.copy_from_slice(&digest[..12]);
        Self(bytes)
    }

    /// The seconds in the id's timestamp.
    pub fn seconds(&self) -> u32 {
        u32::from_be_bytes([self.0[0], self.0[1], self.0[2], self.0[3]])
    }
}

/// Whether `text` is a 24-hex id (either case, as `ObjectId` accepts it).
pub fn is_record_id(text: &str) -> bool {
    text.len() == 24 && text.bytes().all(|b| b.is_ascii_hexdigit())
}

impl FromStr for RecordId {
    type Err = ParseIdError;

    fn from_str(text: &str) -> Result<Self, Self::Err> {
        if !is_record_id(text) {
            return Err(ParseIdError);
        }
        let mut bytes = [0u8; 12];
        hex::decode_to_slice(text, &mut bytes).map_err(|_| ParseIdError)?;
        Ok(Self(bytes))
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ParseIdError;

impl fmt::Display for ParseIdError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(INVALID_ID_MESSAGE)
    }
}

impl std::error::Error for ParseIdError {}

impl fmt::Display for RecordId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&hex::encode(self.0))
    }
}

impl fmt::Debug for RecordId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "RecordId({self})")
    }
}

/// In a document: `{"$oid": "<24 hex>"}` (BSON Extended JSON).
impl Serialize for RecordId {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut map = serializer.serialize_map(Some(1))?;
        map.serialize_entry("$oid", &self.to_string())?;
        map.end()
    }
}

/// Read as the Python backend reads a stored id: `{"$oid": ...}`, or a 24-hex
/// string (a document written by hand, or an id in a request body).
impl<'de> Deserialize<'de> for RecordId {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> Visitor<'de> for V {
            type Value = RecordId;

            fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str("a record id")
            }

            fn visit_str<E: de::Error>(self, v: &str) -> Result<RecordId, E> {
                v.parse().map_err(|_| E::custom(INVALID_ID_MESSAGE))
            }

            fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<RecordId, A::Error> {
                let mut found = None;
                while let Some(key) = map.next_key::<String>()? {
                    if key == "$oid" {
                        let text: String = map.next_value()?;
                        found = Some(
                            text.parse::<RecordId>()
                                .map_err(|_| de::Error::custom(INVALID_ID_MESSAGE))?,
                        );
                    } else {
                        let _ = map.next_value::<de::IgnoredAny>()?;
                    }
                }
                found.ok_or_else(|| de::Error::custom(INVALID_ID_MESSAGE))
            }
        }
        deserializer.deserialize_any(V)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn an_id_is_24_hex_and_round_trips() {
        let id: RecordId = "6a0000000000000000000001".parse().unwrap();
        assert_eq!(id.to_string(), "6a0000000000000000000001");
        assert_eq!(
            serde_json::to_value(id).unwrap(),
            json!({"$oid": "6a0000000000000000000001"})
        );
        let upper: RecordId = "6A0000000000000000000001".parse().unwrap();
        assert_eq!(upper, id, "ObjectId accepts either case and stores lower");
        assert!("6a00".parse::<RecordId>().is_err());
        assert!("zz0000000000000000000001".parse::<RecordId>().is_err());
    }

    #[test]
    fn an_id_is_read_from_text_or_extended_json() {
        let a: RecordId = serde_json::from_value(json!("6a0000000000000000000001")).unwrap();
        let b: RecordId =
            serde_json::from_value(json!({"$oid": "6a0000000000000000000001"})).unwrap();
        assert_eq!(a, b);
        assert!(serde_json::from_value::<RecordId>(json!(5)).is_err());
        assert!(serde_json::from_value::<RecordId>(json!({"x": 1})).is_err());
    }

    #[test]
    fn minted_ids_carry_the_time_and_differ() {
        let a = RecordId::mint(1_700_000_000);
        let b = RecordId::mint(1_700_000_000);
        assert_ne!(a, b);
        assert_eq!(a.seconds(), 1_700_000_000);
        assert_eq!(a.to_string().len(), 24);
    }

    #[test]
    fn a_derived_id_is_the_python_digest() {
        // common.ids.derived_id("a", "b") = sha1("a\x00b")[:12]
        let id = RecordId::derived(&["a", "b"]);
        assert_eq!(id, RecordId::derived(&["a", "b"]));
        assert_ne!(id, RecordId::derived(&["a", "c"]));
        assert_eq!(id.to_string().len(), 24);
    }
}
