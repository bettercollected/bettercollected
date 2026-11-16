//! Typed documents of the tables the route groups read and write first.
//!
//! Each is the Rust twin of a Python `Record` class: the same keys, every one
//! always written (`None` as `null`, defaults written out), unknown stored keys
//! ignored on read, and the Python defaults on read of a missing key. A part
//! that is itself a large model (a form's fields, a theme, an answer set) is
//! carried as `serde_json::Value` already in document form: the data layer
//! reads and writes it unchanged and leaves its content to the module that owns
//! that model. The golden tests (`tests/records.rs`) hold each type to the
//! document Python writes.

pub mod audit_event;
pub mod form;
pub mod form_response;
pub mod workspace;
pub mod workspace_user;

pub use audit_event::WorkspaceAuditEvent;
pub use form::Form;
pub use form_response::FormResponse;
pub use workspace::Workspace;
pub use workspace_user::WorkspaceUser;
