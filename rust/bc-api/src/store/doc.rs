//! Reading values out of a `doc` JSONB document. The codec lives in `bc-db`
//! (`bc_db::value`); these are re-exported so the store modules keep their
//! imports.

// `truthy` reads a flag as pydantic reads a `bool` (`"true"` and `1` are on); a
// policy that must not fail open reads `flag` and treats `Unreadable` as "ask Python".
pub use bc_db::value::{Flag, flag, id_text, lax_bool, truthy};
