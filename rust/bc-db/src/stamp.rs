//! The two ways a document holds a point in time.
//!
//! * [`Stamp`]: what `datetime.isoformat()` writes, a string. Most tables carry
//!   `bson_encoders = {datetime: isoformat}`, so their `created_at` and every
//!   other datetime is `"2026-01-02T03:04:05.678901+00:00"`. A naive value (no
//!   offset) stays naive and a value with another offset keeps it, as Python
//!   keeps it.
//! * [`BsonDate`]: a table without that encoder stores `{"$date": ...}` (BSON
//!   Extended JSON, relaxed): `"2026-01-02T03:04:05.678Z"`, milliseconds, UTC.
//!
//! Both are read the way pydantic reads a datetime out of a stored document: an
//! ISO 8601 string (`T` or a space; `Z`, `+HH:MM`, `+HHMM` or none), a
//! date-only string, `{"$date": string | {"$numberLong": ms} | ms}` and a number
//! (seconds, or milliseconds above 2e10).

use std::fmt::Write as _;

use chrono::{DateTime, FixedOffset, NaiveDate, NaiveDateTime, NaiveTime, TimeZone, Timelike, Utc};
use serde::de::{Deserialize, Deserializer, Error as _};
use serde::ser::{Serialize, SerializeMap, Serializer};
use serde_json::Value;

/// A Python `datetime` as the document holds it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Stamp {
    Naive(NaiveDateTime),
    Aware(DateTime<FixedOffset>),
}

impl Stamp {
    pub fn utc(at: DateTime<Utc>) -> Self {
        Stamp::Aware(at.fixed_offset())
    }

    /// The instant; a naive value is taken as UTC (as `row_values` does).
    pub fn to_utc(&self) -> DateTime<Utc> {
        match self {
            Stamp::Naive(n) => Utc.from_utc_datetime(n),
            Stamp::Aware(a) => a.with_timezone(&Utc),
        }
    }

    /// `datetime.isoformat()`: microseconds only when not zero, the offset only
    /// when aware.
    pub fn isoformat(&self) -> String {
        let (naive, offset) = match self {
            Stamp::Naive(n) => (*n, None),
            Stamp::Aware(a) => (a.naive_local(), Some(*a.offset())),
        };
        let mut out = naive.format("%Y-%m-%dT%H:%M:%S").to_string();
        let micros = naive.nanosecond() / 1000;
        if micros != 0 {
            let _ = write!(out, ".{micros:06}");
        }
        if let Some(offset) = offset {
            let secs = offset.local_minus_utc();
            let sign = if secs < 0 { '-' } else { '+' };
            let secs = secs.abs();
            let _ = write!(out, "{sign}{:02}:{:02}", secs / 3600, secs % 3600 / 60);
            if secs % 60 != 0 {
                let _ = write!(out, ":{:02}", secs % 60);
            }
        }
        out
    }

    /// Reads a stored value (see the module docs); `None` when it is not a
    /// point in time.
    pub fn from_value(value: &Value) -> Option<Stamp> {
        match value {
            Value::String(s) => parse_iso(s),
            Value::Number(n) => from_number(n.as_f64()?),
            Value::Object(o) => match o.get("$date")? {
                Value::String(s) => parse_iso(s),
                Value::Number(n) => millis(n.as_f64()?),
                Value::Object(d) => millis(d.get("$numberLong")?.as_str()?.parse::<f64>().ok()?),
                _ => None,
            },
            _ => None,
        }
    }
}

fn from_number(n: f64) -> Option<Stamp> {
    // pydantic: a number above 2e10 is milliseconds, else seconds
    if n.abs() > 2e10 {
        millis(n)
    } else {
        millis(n * 1000.0)
    }
}

fn millis(ms: f64) -> Option<Stamp> {
    if !ms.is_finite() {
        return None;
    }
    #[allow(clippy::cast_possible_truncation)]
    let at = DateTime::<Utc>::from_timestamp_millis(ms.floor() as i64)?;
    Some(Stamp::utc(at))
}

/// ISO 8601 as pydantic accepts it for a datetime.
pub fn parse_iso(text: &str) -> Option<Stamp> {
    let (date_part, rest) = match text.find(['T', 't', ' ']) {
        Some(i) => (&text[..i], Some(&text[i + 1..])),
        None => (text, None),
    };
    let date = NaiveDate::parse_from_str(date_part, "%Y-%m-%d").ok()?;
    if date_part.len() != 10 {
        return None;
    }
    let Some(rest) = rest else {
        return Some(Stamp::Naive(date.and_time(NaiveTime::MIN)));
    };
    // split the zone off the time
    let (time_part, zone) = match rest.find(['Z', 'z', '+', '-']) {
        Some(i) => (&rest[..i], Some(&rest[i..])),
        None => (rest, None),
    };
    let time = parse_time(time_part)?;
    let naive = date.and_time(time);
    match zone {
        None => Some(Stamp::Naive(naive)),
        Some(z) => {
            let offset = parse_zone(z)?;
            Some(Stamp::Aware(offset.from_local_datetime(&naive).single()?))
        }
    }
}

fn parse_time(text: &str) -> Option<NaiveTime> {
    let (clock, fraction) = match text.split_once('.') {
        Some((c, f)) => (c, Some(f)),
        None => (text, None),
    };
    let mut parts = clock.split(':');
    let hour: u32 = two_digits(parts.next()?)?;
    let minute: u32 = two_digits(parts.next()?)?;
    let second: u32 = match parts.next() {
        Some(s) => two_digits(s)?,
        None => 0,
    };
    if parts.next().is_some() {
        return None;
    }
    let micros: u32 = match fraction {
        None => 0,
        Some(f) => {
            if f.is_empty() || !f.bytes().all(|b| b.is_ascii_digit()) {
                return None;
            }
            // more than 6 digits are truncated
            let mut digits: String = f.chars().take(6).collect();
            while digits.len() < 6 {
                digits.push('0');
            }
            digits.parse().ok()?
        }
    };
    NaiveTime::from_hms_micro_opt(hour, minute, second, micros)
}

fn two_digits(text: &str) -> Option<u32> {
    if text.len() == 2 && text.bytes().all(|b| b.is_ascii_digit()) {
        text.parse().ok()
    } else {
        None
    }
}

fn parse_zone(text: &str) -> Option<FixedOffset> {
    if text == "Z" || text == "z" {
        return FixedOffset::east_opt(0);
    }
    let sign = match text.as_bytes().first()? {
        b'+' => 1,
        b'-' => -1,
        _ => return None,
    };
    let digits = text[1..].replace(':', "");
    if !digits.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let (h, m) = match digits.len() {
        2 => (digits.parse::<i32>().ok()?, 0),
        4 => (
            digits[..2].parse::<i32>().ok()?,
            digits[2..].parse::<i32>().ok()?,
        ),
        _ => return None,
    };
    if m > 59 {
        return None;
    }
    FixedOffset::east_opt(sign * (h * 3600 + m * 60))
}

impl Serialize for Stamp {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.serialize_str(&self.isoformat())
    }
}

impl<'de> Deserialize<'de> for Stamp {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let value = Value::deserialize(deserializer)?;
        Stamp::from_value(&value).ok_or_else(|| D::Error::custom("not a datetime"))
    }
}

/// A BSON date in a document: `{"$date": "2026-01-02T03:04:05.678Z"}`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BsonDate(pub DateTime<Utc>);

impl BsonDate {
    /// The relaxed Extended JSON of `bson.json_util`: milliseconds (truncated)
    /// and a `Z`, for an instant from 1970 on; `{"$numberLong": ms}` before.
    pub fn extended_json(&self) -> Value {
        let at = self.0;
        if at.timestamp() >= 0 {
            let ms = at.timestamp_subsec_micros() / 1000;
            let fraction = if ms == 0 {
                String::new()
            } else {
                format!(".{ms:03}")
            };
            let text = format!("{}{}Z", at.format("%Y-%m-%dT%H:%M:%S"), fraction);
            serde_json::json!({ "$date": text })
        } else {
            let ms = at.timestamp() * 1000 + i64::from(at.timestamp_subsec_micros() / 1000);
            serde_json::json!({ "$date": { "$numberLong": ms.to_string() } })
        }
    }
}

impl Serialize for BsonDate {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut map = serializer.serialize_map(Some(1))?;
        match self.extended_json() {
            Value::Object(o) => {
                for (k, v) in o {
                    map.serialize_entry(&k, &v)?;
                }
            }
            _ => unreachable!("extended_json builds an object"),
        }
        map.end()
    }
}

impl<'de> Deserialize<'de> for BsonDate {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        Stamp::deserialize(deserializer).map(|s| BsonDate(s.to_utc()))
    }
}

/// What a record's `created_at` / `updated_at` fields are, whichever of the two
/// forms the table stores.
pub trait Moment: Sized {
    fn to_utc(&self) -> DateTime<Utc>;
    fn from_utc(at: DateTime<Utc>) -> Self;
}

impl Moment for Stamp {
    fn to_utc(&self) -> DateTime<Utc> {
        Stamp::to_utc(self)
    }
    fn from_utc(at: DateTime<Utc>) -> Self {
        Stamp::utc(at)
    }
}

impl Moment for BsonDate {
    fn to_utc(&self) -> DateTime<Utc> {
        self.0
    }
    fn from_utc(at: DateTime<Utc>) -> Self {
        BsonDate(at)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn stamp(text: &str) -> Stamp {
        parse_iso(text).unwrap_or_else(|| panic!("{text}"))
    }

    #[test]
    fn isoformat_matches_python() {
        for text in [
            "2026-01-02T03:04:05.678901+00:00",
            "2026-01-02T03:04:05+00:00",
            "2026-03-04T05:06:07.891234+02:00",
            "2026-03-04T05:06:07.891234",
            "2026-03-04T05:06:07",
            "2026-03-04T05:06:07.000500-05:30",
        ] {
            assert_eq!(stamp(text).isoformat(), text);
        }
    }

    #[test]
    fn the_zulu_and_compact_forms_are_read() {
        assert_eq!(
            stamp("2026-01-02T03:04:05Z").isoformat(),
            "2026-01-02T03:04:05+00:00"
        );
        assert_eq!(
            stamp("2026-01-02 03:04:05+0200").isoformat(),
            "2026-01-02T03:04:05+02:00"
        );
        assert_eq!(
            stamp("2026-01-02T03:04:05.1234567Z").isoformat(),
            "2026-01-02T03:04:05.123456+00:00"
        );
        assert_eq!(
            stamp("2026-01-02T03:04:05.5").isoformat(),
            "2026-01-02T03:04:05.500000"
        );
        assert_eq!(stamp("2026-01-02").isoformat(), "2026-01-02T00:00:00");
        assert!(parse_iso("not a date").is_none());
        assert!(parse_iso("2026-13-02T00:00:00Z").is_none());
        assert!(parse_iso("2026-01-02T25:00:00Z").is_none());
    }

    #[test]
    fn stored_forms_of_a_date_are_read() {
        let want = Stamp::from_value(&json!("2026-01-02T03:04:05.678Z")).unwrap();
        assert_eq!(
            Stamp::from_value(&json!({"$date": "2026-01-02T03:04:05.678Z"})),
            Some(want)
        );
        let ms = want.to_utc().timestamp_millis();
        assert_eq!(
            Stamp::from_value(&json!({"$date": {"$numberLong": ms.to_string()}}))
                .map(|s| s.to_utc()),
            Some(want.to_utc())
        );
        assert_eq!(
            Stamp::from_value(&json!({"$date": ms})).map(|s| s.to_utc()),
            Some(want.to_utc())
        );
        assert_eq!(Stamp::from_value(&json!(true)), None);
    }

    #[test]
    fn a_bson_date_is_written_like_json_util() {
        let at = Utc.with_ymd_and_hms(2026, 1, 2, 3, 4, 5).unwrap();
        assert_eq!(
            BsonDate(at).extended_json(),
            json!({"$date": "2026-01-02T03:04:05Z"})
        );
        let with_micros = DateTime::from_timestamp(at.timestamp(), 678_901_000).unwrap();
        assert_eq!(
            BsonDate(with_micros).extended_json(),
            json!({"$date": "2026-01-02T03:04:05.678Z"})
        );
        let before = Utc.with_ymd_and_hms(1969, 12, 31, 23, 59, 59).unwrap();
        assert_eq!(
            BsonDate(before).extended_json(),
            json!({"$date": {"$numberLong": "-1000"}})
        );
        let back: BsonDate =
            serde_json::from_value(serde_json::to_value(BsonDate(at)).unwrap()).unwrap();
        assert_eq!(back, BsonDate(at));
    }
}
