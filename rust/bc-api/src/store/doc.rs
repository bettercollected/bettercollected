//! Reading values out of a `doc` JSONB document. The codec lives in `bc-db`
//! (`bc_db::value`); these are re-exported so the store modules keep their
//! imports.

pub use bc_db::value::{id_text, truthy};
