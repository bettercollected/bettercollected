//! bc-api: the edge of the bettercollected backend.
//!
//! A request is answered by Rust only when its route group is switched on
//! (`BC_RUST_ROUTES`); every other request is forwarded to the Python backend
//! ([`proxy`]). Switching a group off puts its routes back on Python with one
//! setting.
//!
//! * [`state`]: what every handler shares.
//! * [`proxy`]: the pass-through.
//! * [`groups`]: the route groups, one module each; [`groups::ALL`] is the
//!   registry the switch reads.
//! * [`store`]: the queries, one module per table family.
//! * [`app`]: the router, assembled from the groups that are switched on.

pub mod app;
pub mod groups;
pub mod proxy;
pub mod state;
pub mod store;
