//! The settings store reader: what the Python loader (`common/settings`) does,
//! for the reader `backend`.
//!
//! The admin portal writes signed (and, for secrets, sealed) rows into schema
//! `settings`; each service reads its own security-barrier view, verifies every
//! row against the signed manifest and its own signature, and opens secrets with
//! keys derived from `SETTINGS_MASTER_KEY`. Resolution order: a non-empty
//! environment value, then the verified stored value, then the default.
//!
//! * [`canonical`]: the signed bytes of a row and of the manifest.
//! * [`crypto`]: key derivation, signatures, the envelope of a secret.
//! * [`registry`]: the keys the backend may read (generated from the Python
//!   registry) and the typed reading of a value.
//! * [`verify`]: which rows are accepted.
//! * [`disk`]: the signed disk snapshot (rollback floor, database-down start).
//! * [`pg`]: reading the two views.
//! * [`runtime`]: the loader, its failure policy, live (class H) values, polling.

pub mod canonical;
pub mod crypto;
pub mod disk;
pub mod pg;
pub mod registry;
pub mod runtime;
pub mod verify;

pub use registry::Registry;
pub use runtime::{
    LoaderConfig, Mode, Origin, SnapshotSource, SourceUnavailable, StoreError, StoreRuntime, load,
};
