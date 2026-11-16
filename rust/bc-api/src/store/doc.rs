//! Reading values out of a `doc` JSONB document.

use serde_json::Value;

/// An id as the document stores it: a plain string or `{"$oid": ...}`.
pub fn id_text(value: Option<&Value>) -> Option<String> {
    match value? {
        Value::String(s) => Some(s.clone()),
        Value::Object(o) => o.get("$oid").and_then(Value::as_str).map(str::to_string),
        _ => None,
    }
}

/// `true` only for a JSON `true`; absent, null and anything else are false.
pub fn truthy(value: Option<&Value>) -> bool {
    matches!(value, Some(Value::Bool(true)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn ids_come_as_text_or_extended_json() {
        assert_eq!(id_text(Some(&json!("a1"))).as_deref(), Some("a1"));
        assert_eq!(id_text(Some(&json!({"$oid": "a1"}))).as_deref(), Some("a1"));
        assert_eq!(id_text(Some(&json!(5))), None);
        assert_eq!(id_text(None), None);
    }

    #[test]
    fn only_a_json_true_is_true() {
        assert!(truthy(Some(&json!(true))));
        for no in [json!(false), json!(null), json!("true"), json!(1)] {
            assert!(!truthy(Some(&no)));
        }
        assert!(!truthy(None));
    }
}
