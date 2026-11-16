//! The queries, one module per table family. This service owns no schema: it
//! reads the tables the Python backend's Alembic chain defines (head
//! `bc_db::EXPECTED_HEAD`).
//!
//! Every table is `id`, `doc` JSONB and a few columns GENERATED from `doc`
//! (`common/common/db/spine.py`); a query uses the generated columns exactly as
//! the Python repositories do and reads the rest out of `doc`.

pub mod doc;
pub mod origins;
pub mod workspaces;
