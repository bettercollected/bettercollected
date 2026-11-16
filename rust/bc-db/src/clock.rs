//! The clock every stamp reads (`common/clock.py`: one function, so a test can
//! fix the time in one place). A `Db` owns one; `created_at`, `updated_at`,
//! tombstone times and new ids all come from it.

use std::fmt::Debug;
use std::sync::{Arc, Mutex, PoisonError};
use std::time::{SystemTime, UNIX_EPOCH};

use chrono::{DateTime, Duration, Utc};

/// The current time, aware UTC, at the microsecond precision of a Python
/// `datetime`.
pub trait Clock: Send + Sync + Debug {
    fn now(&self) -> DateTime<Utc>;
}

pub type SharedClock = Arc<dyn Clock>;

/// The wall clock, truncated to microseconds (Python's `datetime.now`).
#[derive(Debug, Clone, Copy, Default)]
pub struct SystemClock;

impl Clock for SystemClock {
    fn now(&self) -> DateTime<Utc> {
        // std's clock, so chrono needs no platform time-zone crates
        let since = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default();
        let micros = i64::try_from(since.as_micros()).unwrap_or(i64::MAX);
        DateTime::from_timestamp_micros(micros).unwrap_or_default()
    }
}

/// A clock a test sets and moves by hand.
#[derive(Debug)]
pub struct FixedClock(Mutex<DateTime<Utc>>);

impl FixedClock {
    pub fn new(at: DateTime<Utc>) -> Self {
        Self(Mutex::new(at))
    }

    pub fn set(&self, at: DateTime<Utc>) {
        *self.0.lock().unwrap_or_else(PoisonError::into_inner) = at;
    }

    /// The instant (the same as `Clock::now`, without importing the trait).
    pub fn now_utc(&self) -> DateTime<Utc> {
        *self.0.lock().unwrap_or_else(PoisonError::into_inner)
    }

    pub fn advance(&self, by: Duration) {
        let mut at = self.0.lock().unwrap_or_else(PoisonError::into_inner);
        *at += by;
    }
}

impl Clock for FixedClock {
    fn now(&self) -> DateTime<Utc> {
        *self.0.lock().unwrap_or_else(PoisonError::into_inner)
    }
}

pub fn system() -> SharedClock {
    Arc::new(SystemClock)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn the_system_clock_has_microsecond_precision() {
        let now = SystemClock.now();
        assert_eq!(now.timestamp_subsec_nanos() % 1000, 0);
    }

    #[test]
    fn a_fixed_clock_stands_still_until_moved() {
        let at = Utc.with_ymd_and_hms(2026, 1, 2, 3, 4, 5).unwrap();
        let clock = FixedClock::new(at);
        assert_eq!(clock.now(), at);
        clock.advance(Duration::seconds(90));
        assert_eq!(clock.now(), at + Duration::seconds(90));
        clock.set(at);
        assert_eq!(clock.now(), at);
    }
}
