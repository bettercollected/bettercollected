//! `app.form_responses` (`FormResponseDocument`).
//!
//! `answers`, `hidden_fields`, `internal_answers` and the feedback messages are
//! stored encrypted (a `{"$binary": ...}` value): this type carries them as
//! they are and never decrypts, logs or queries them.

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::id::RecordId;
use crate::impl_record;
use crate::stamp::Stamp;
use crate::value::lax;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct FormResponse {
    #[serde(rename = "_id", default)]
    pub id: Option<RecordId>,
    pub created_at: Option<Stamp>,
    pub updated_at: Option<Stamp>,

    #[serde(default)]
    pub response_id: Option<String>,
    #[serde(default)]
    pub form_id: Option<String>,
    #[serde(default)]
    pub provider: Option<String>,
    #[serde(default)]
    pub respondent_email: Option<String>,
    #[serde(default)]
    pub answers: Option<Value>,
    #[serde(default)]
    pub hidden_fields: Option<Value>,
    #[serde(default)]
    pub internal_answers: Option<Value>,
    #[serde(default)]
    pub internal_answers_meta: Option<Value>,
    #[serde(default, deserialize_with = "lax::opt_i64")]
    pub internal_answers_version: Option<i64>,
    #[serde(default)]
    pub respondent_feedback: Option<Value>,
    #[serde(default, deserialize_with = "lax::opt_i64")]
    pub form_version: Option<i64>,
    #[serde(default)]
    pub published_at: Option<Stamp>,
    #[serde(default)]
    pub consent: Option<Value>,
    #[serde(default)]
    pub expiration: Option<String>,
    #[serde(default)]
    pub expiration_type: Option<String>,
    #[serde(default)]
    pub state: Option<Value>,
    #[serde(rename = "dataOwnerIdentifierType", default)]
    pub data_owner_identifier_type: Option<String>,
    #[serde(rename = "dataOwnerIdentifier", default)]
    pub data_owner_identifier: Option<String>,
    #[serde(default)]
    pub anonymous_identity: Option<String>,
    #[serde(default)]
    pub submission_uuid: Option<String>,
    #[serde(default)]
    pub ai_notice_shown_at: Option<Stamp>,
    #[serde(default)]
    pub shared_as_choices: Option<Vec<String>>,
    #[serde(default)]
    pub ai_notice_provider_name: Option<String>,
    #[serde(default)]
    pub ending_id: Option<String>,
    #[serde(default)]
    pub csv_import_id: Option<String>,
    #[serde(default)]
    pub submission_source: Option<Value>,
    /// The workspace the response was collected in; absent only on responses
    /// stored before it existed.
    #[serde(default)]
    pub workspace_id: Option<RecordId>,
}

impl_record!(FormResponse, "form_responses", Stamp);
