//! The feature switches `GET /workspaces/{id}/permissions` reports, each off
//! by default, under the names the Python settings use.

use crate::ConfigError;
use crate::source::Settings;

#[derive(Debug, Clone, Default, PartialEq, Eq)]
#[allow(clippy::struct_excessive_bools)]
pub struct Flags {
    pub field_rules: bool,
    pub choice_logic: bool,
    pub save_drafts: bool,
    pub captcha: bool,
    pub csv_import: bool,
    pub new_question_types: bool,
    pub address_question: bool,
    pub address_lookup: bool,
    pub signature_question: bool,
    pub option_sources: bool,
    pub reusable_sections: bool,
    pub layout_containers: bool,
    pub daybreak_preset: bool,
    pub form_revisions_ui: bool,
    pub audit_log_ui: bool,
    pub response_revisions: bool,
    pub submissions_api: bool,
    pub form_embed: bool,
    pub form_access: bool,
    pub form_promotion: bool,
    pub api_key_roles: bool,
    pub reporting: bool,
    pub app_theme_pigment: bool,
}

impl Flags {
    /// `offered_gated_presets`: the gated presets whose switch is on, in the
    /// order of `constants/themes.py` `GATED_PRESETS`.
    pub fn offered_presets(&self) -> Vec<&'static str> {
        let mut out = Vec::new();
        if self.daybreak_preset {
            out.push("Daybreak");
        }
        if self.app_theme_pigment {
            out.push("Pigment");
        }
        out
    }

    pub fn from_settings(settings: &Settings) -> Result<Flags, ConfigError> {
        let flag = |name: &str| settings.flag(name).map(|v| v.unwrap_or(false));
        Ok(Flags {
            field_rules: flag("FIELD_RULES_ENABLED")?,
            choice_logic: flag("CHOICE_LOGIC_ENABLED")?,
            save_drafts: flag("SAVE_DRAFTS_ENABLED")?,
            captcha: flag("CAPTCHA_ENABLED")?,
            csv_import: flag("CSV_IMPORT_ENABLED")?,
            new_question_types: flag("NEW_QUESTION_TYPES_ENABLED")?,
            address_question: flag("ADDRESS_QUESTION_ENABLED")?,
            address_lookup: flag("ADDRESS_LOOKUP_ENABLED")?,
            signature_question: flag("SIGNATURE_QUESTION_ENABLED")?,
            option_sources: flag("OPTION_SOURCES_ENABLED")?,
            reusable_sections: flag("REUSABLE_SECTIONS_ENABLED")?,
            layout_containers: flag("LAYOUT_CONTAINERS_ENABLED")?,
            daybreak_preset: flag("DAYBREAK_PRESET_ENABLED")?,
            form_revisions_ui: flag("FORM_REVISIONS_UI_ENABLED")?,
            audit_log_ui: flag("AUDIT_LOG_UI_ENABLED")?,
            response_revisions: flag("RESPONSE_REVISIONS_ENABLED")?,
            submissions_api: flag("SUBMISSIONS_API_ENABLED")?,
            form_embed: flag("FORM_EMBED_ENABLED")?,
            form_access: flag("FORM_ACCESS_ENABLED")?,
            form_promotion: flag("FORM_PROMOTION_ENABLED")?,
            api_key_roles: flag("API_KEY_ROLES_ENABLED")?,
            reporting: flag("REPORTING_ENABLED")?,
            app_theme_pigment: flag("APP_THEME_PIGMENT_ENABLED")?,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tests::settings;

    #[test]
    fn every_switch_is_off_by_default() {
        assert_eq!(
            Flags::from_settings(&settings(&[])).unwrap(),
            Flags::default()
        );
    }

    #[test]
    fn a_switch_is_read_under_the_python_name() {
        let flags = Flags::from_settings(&settings(&[("CAPTCHA_ENABLED", "yes")])).unwrap();
        assert!(flags.captcha && !flags.field_rules);
    }

    #[test]
    fn an_invalid_value_stops_the_start_without_echoing_it() {
        let err = Flags::from_settings(&settings(&[("CAPTCHA_ENABLED", "maybe")])).unwrap_err();
        assert!(err.0.contains("CAPTCHA_ENABLED") && !err.0.contains("maybe"));
    }

    #[test]
    fn gated_presets_follow_the_python_order() {
        let flags = Flags {
            daybreak_preset: true,
            app_theme_pigment: true,
            ..Flags::default()
        };
        assert_eq!(flags.offered_presets(), vec!["Daybreak", "Pigment"]);
    }
}
