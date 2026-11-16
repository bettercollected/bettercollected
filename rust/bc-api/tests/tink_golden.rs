//! The Python backend's ciphertext opens in Rust, and the other way round.

use base64::engine::general_purpose::STANDARD;
use base64::Engine;
use bc_api::crypto::{CryptoError, Keyset};
use serde_json::Value;

fn vector() -> Value {
    serde_json::from_str(include_str!("golden/tink_vector.json")).unwrap()
}

#[test]
fn opens_values_written_by_python() {
    let v = vector();
    let mut n = 0;
    for case in v["cases"].as_array().unwrap() {
        let keyset = Keyset::parse(case["keyset"].as_str().unwrap()).unwrap();
        for value in case["values"].as_array().unwrap() {
            let stored = STANDARD
                .decode(value["stored_b64"].as_str().unwrap())
                .unwrap();
            let ctx = STANDARD
                .decode(value["context_b64"].as_str().unwrap())
                .unwrap();
            let opened = keyset
                .decrypt(
                    value["workspace_id"].as_str().unwrap(),
                    value["form_id"].as_str().unwrap(),
                    &stored,
                    &ctx,
                )
                .unwrap();
            assert_eq!(opened, value["plaintext"].as_str().unwrap().as_bytes());
            n += 1;
        }
    }
    assert_eq!(n, 6);
}

#[test]
fn refuses_another_workspace_form_context_or_a_flipped_bit() {
    let v = vector();
    let case = &v["cases"][0];
    let keyset = Keyset::parse(case["keyset"].as_str().unwrap()).unwrap();
    let value = &case["values"][0];
    let stored = STANDARD
        .decode(value["stored_b64"].as_str().unwrap())
        .unwrap();
    let ws = value["workspace_id"].as_str().unwrap();
    let form = value["form_id"].as_str().unwrap();
    assert_eq!(
        keyset.decrypt("other", form, &stored, b"").unwrap_err(),
        CryptoError::Unreadable
    );
    assert_eq!(
        keyset.decrypt(ws, "other", &stored, b"").unwrap_err(),
        CryptoError::Unreadable
    );
    assert_eq!(
        keyset.decrypt(ws, form, &stored, b"ctx").unwrap_err(),
        CryptoError::Unreadable
    );
    let mut flipped = stored.clone();
    let last = flipped.len() - 1;
    flipped[last] ^= 1;
    assert_eq!(
        keyset.decrypt(ws, form, &flipped, b"").unwrap_err(),
        CryptoError::Unreadable
    );
    // plaintext that is not a v1 value is not ciphertext
    assert_eq!(
        keyset.decrypt(ws, form, b"plain", b"").unwrap_err(),
        CryptoError::NotCiphertext
    );
    // errors never carry the value
    assert!(!CryptoError::Unreadable.to_string().contains("plain"));
}

#[test]
fn a_keyset_that_is_not_aes_gcm_tink_is_refused() {
    let bad = r#"{"primaryKeyId":1,"key":[{"keyData":{"typeUrl":"type.googleapis.com/google.crypto.tink.AesCtrHmacAeadKey","value":"AA==","keyMaterialType":"SYMMETRIC"},"status":"ENABLED","keyId":1,"outputPrefixType":"TINK"}]}"#;
    assert!(matches!(Keyset::parse(bad), Err(CryptoError::Keyset(_))));
    assert!(matches!(
        Keyset::parse("not a keyset"),
        Err(CryptoError::Keyset(_))
    ));
}

/// What Rust seals, Python opens: writes a file the contract script reads
/// back with `golden_tink.py --check` (run when RUST_SEALED_OUT is set).
#[test]
fn rust_sealed_value_for_python_to_open() {
    let Ok(out) = std::env::var("RUST_SEALED_OUT") else {
        return;
    };
    let v = vector();
    let case = &v["cases"][0];
    let keyset = Keyset::parse(case["keyset"].as_str().unwrap()).unwrap();
    let ctx = b"[\"a\",\"b\"]";
    let sealed = keyset
        .encrypt_with_nonce("ws1", "form1", "written by rust".as_bytes(), ctx, [7u8; 12])
        .unwrap();
    let file = serde_json::json!({
        "name": case["name"], "workspace_id": "ws1", "form_id": "form1",
        "context_b64": STANDARD.encode(ctx), "plaintext": "written by rust",
        "stored_b64": STANDARD.encode(sealed),
    });
    std::fs::write(out, file.to_string()).unwrap();
}
