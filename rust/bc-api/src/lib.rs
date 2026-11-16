//! bc-api: a spike of a Rust service next to the bettercollected Python
//! backend. It reads the same Postgres schema and verifies the same session
//! cookies, and serves one route.

pub mod auth;
pub mod authz;
pub mod config;
pub mod cors;
pub mod crypto;
pub mod db;
pub mod routes;
