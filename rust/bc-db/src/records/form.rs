//! `app.forms` (`FormDocument`, the `StandardForm` model).
//!
//! The scalar keys and the small `settings` / `state` objects are typed. The
//! large parts (`fields`, `consent`, `theme`, the welcome and ending pages,
//! `actions`, `parameters`, `secrets`) are carried as document-form JSON: a
//! writer that takes them from a request body must normalise them with the
//! form-spec module first, as the Python models do on validation.

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::id::RecordId;
use crate::impl_record;
use crate::stamp::Stamp;
use crate::value::lax;

/// `StandardFormSettings`: every key optional.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct FormSettings {
    #[serde(default)]
    pub embed_url: Option<String>,
    #[serde(default)]
    pub custom_url: Option<String>,
    #[serde(default)]
    pub provider: Option<String>,
    #[serde(default)]
    pub language: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub is_public: Option<bool>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub is_trial: Option<bool>,
    #[serde(default)]
    pub response_data_owner_field: Option<String>,
    #[serde(default)]
    pub response_data_owner_fields: Option<Vec<String>>,
    #[serde(default)]
    pub screens: Option<Value>,
    #[serde(default)]
    pub privacy_policy_url: Option<String>,
    #[serde(default)]
    pub response_expiration: Option<String>,
    #[serde(default)]
    pub response_expiration_type: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub is_response_editable: Option<bool>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub is_closed: Option<bool>,
}

/// `State`: every key optional.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct FormState {
    #[serde(default)]
    pub global_state: Option<Value>,
    #[serde(default)]
    pub processor_state: Option<Value>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub is_locked: Option<bool>,
}

#[allow(clippy::unnecessary_wraps)] // serde `default =` needs the field type
fn default_state() -> Option<FormState> {
    Some(FormState::default())
}

#[allow(clippy::unnecessary_wraps)]
fn default_settings() -> Option<FormSettings> {
    Some(FormSettings::default())
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Form {
    #[serde(rename = "_id", default)]
    pub id: Option<RecordId>,
    pub created_at: Option<Stamp>,
    pub updated_at: Option<Stamp>,

    #[serde(default)]
    pub builder_version: Option<String>,
    #[serde(default)]
    pub form_id: Option<String>,
    #[serde(default)]
    pub imported_form_id: Option<String>,
    #[serde(rename = "type", default)]
    pub form_type: Option<String>,
    #[serde(default)]
    pub title: Option<String>,
    #[serde(default)]
    pub logo: Option<String>,
    #[serde(default)]
    pub logo_position: Option<String>,
    #[serde(default)]
    pub logo_alt: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub use_workspace_logo: Option<bool>,
    #[serde(default)]
    pub cover_image: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub button_text: Option<String>,
    #[serde(default, deserialize_with = "lax::opt_bool")]
    pub is_multi_page: Option<bool>,
    #[serde(default)]
    pub fields: Option<Value>,
    #[serde(default)]
    pub hidden_fields: Option<Vec<String>>,
    #[serde(default)]
    pub consent: Option<Value>,
    #[serde(default = "default_state")]
    pub state: Option<FormState>,
    #[serde(default = "default_settings")]
    pub settings: Option<FormSettings>,
    #[serde(default)]
    pub published_at: Option<Stamp>,
    #[serde(default)]
    pub actions: Option<Value>,
    #[serde(default)]
    pub parameters: Option<Value>,
    #[serde(default)]
    pub secrets: Option<Value>,
    #[serde(default)]
    pub theme: Option<Value>,
    #[serde(default)]
    pub welcome_page: Option<Value>,
    #[serde(default)]
    pub thankyou_page: Option<Value>,
    #[serde(default)]
    pub row_titles: Option<Vec<String>>,
    #[serde(default)]
    pub column_titles: Option<Vec<String>>,
}

impl_record!(Form, "forms", Stamp);
