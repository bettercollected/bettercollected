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

/// The system's random generator could not be read. An id is never minted
/// without it: two processes in that state would mint the same ids and an
/// upsert would overwrite another record's row (Python's `ObjectId` raises).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NoRandomness;

impl fmt::Display for NoRandomness {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("the system random generator is unavailable: no id can be minted")
    }
}

impl std::error::Error for NoRandomness {}

/// What identifies this process in the ids it mints: 5 random bytes and a
/// counter that starts at a random value.
#[derive(Debug)]
pub struct Process {
    random: [u8; 5],
    counter: AtomicU32,
}

impl Process {
    /// Reads the process's randomness from `source` (the system generator in
    /// production, a stand-in in tests). A failing source is an error: there is
    /// no fallback value.
    pub fn from_source<E>(
        source: impl FnOnce(&mut [u8]) -> Result<(), E>,
    ) -> Result<Self, NoRandomness> {
        let mut bytes = [0u8; 8];
        source(&mut bytes).map_err(|_| NoRandomness)?;
        let mut random = [0u8; 5];
        random.copy_from_slice(&bytes[..5]);
        let start = u32::from_be_bytes([0, bytes[5], bytes[6], bytes[7]]);
        Ok(Self {
            random,
            counter: AtomicU32::new(start),
        })
    }

    /// A new id stamped with `seconds` since the epoch.
    pub fn mint(&self, seconds: u32) -> RecordId {
        let counter = self.counter.fetch_add(1, Ordering::Relaxed) & 0x00ff_ffff;
        let mut bytes = [0u8; 12];
        bytes[..4].copy_from_slice(&seconds.to_be_bytes());
        bytes[4..9].copy_from_slice(&self.random);
        bytes[9..].copy_from_slice(&counter.to_be_bytes()[1..]);
        RecordId(bytes)
    }
}

/// The process's identity, read once from the system generator. A failure is
/// not remembered: the next call tries again, and no id is minted meanwhile.
fn process() -> Result<&'static Process, NoRandomness> {
    static P: OnceLock<Process> = OnceLock::new();
    if let Some(p) = P.get() {
        return Ok(p);
    }
    let fresh = Process::from_source(getrandom::getrandom)?;
    Ok(P.get_or_init(|| fresh))
}

impl RecordId {
    pub const fn from_bytes(bytes: [u8; 12]) -> Self {
        Self(bytes)
    }

    /// A new id stamped with `seconds` since the epoch (the clock's now).
    /// [`NoRandomness`] when the system generator cannot be read.
    pub fn mint(seconds: u32) -> Result<Self, NoRandomness> {
        Ok(process()?.mint(seconds))
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
        let a = RecordId::mint(1_700_000_000).unwrap();
        let b = RecordId::mint(1_700_000_000).unwrap();
        assert_ne!(a, b);
        assert_eq!(a.seconds(), 1_700_000_000);
        assert_eq!(a.to_string().len(), 24);
    }

    #[test]
    fn a_failing_random_source_mints_nothing() {
        let failing = Process::from_source(|_| Err::<(), _>("no entropy"));
        assert_eq!(failing.unwrap_err(), NoRandomness);
        // a working source: ids differ by the counter, and carry the source's bytes
        let source = |buf: &mut [u8]| -> Result<(), ()> {
            buf.copy_from_slice(&[1, 2, 3, 4, 5, 0, 0, 7]);
            Ok(())
        };
        let p = Process::from_source(source).unwrap();
        let (a, b) = (p.mint(9), p.mint(9));
        assert_eq!(a.to_string(), "000000090102030405000007");
        assert_eq!(b.to_string(), "000000090102030405000008");
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
