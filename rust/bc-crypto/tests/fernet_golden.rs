#![allow(
    clippy::unwrap_used,
    clippy::many_single_char_names,
    clippy::single_match_else
)]
//! The Fernet key ring: tokens the Python backend sealed open here, a token
//! sealed here is byte for byte the one Python seals, and a Rust-sealed token
//! opens in Python (`rust/contract/golden_crypto.py check-fernet`).

use bc_crypto::CryptoError;
use bc_crypto::fernet::{FernetRing, generate_key};
use bc_crypto::sealed;
use serde_json::{Value, json};

fn vector() -> Value {
    serde_json::from_str(include_str!("golden/fernet_vector.json")).unwrap()
}

fn iv() -> [u8; 16] {
    let mut iv = [0u8; 16];
    iv.copy_from_slice(&hex::decode(vector()["iv_hex"].as_str().unwrap()).unwrap());
    iv
}

#[test]
fn every_case_python_decided_is_decided_the_same_here() {
    let v = vector();
    let (mut opened, mut refused) = (0, 0);
    for case in v["cases"].as_array().unwrap() {
        let name = case["name"].as_str().unwrap();
        let ring = FernetRing::parse(case["ring"].as_str().unwrap()).unwrap();
        let ttl = case["ttl"].as_u64();
        let token = case["token"].as_str().unwrap();
        let got = match case["now"].as_u64() {
            Some(now) => ring.open_at(token, ttl, now),
            None => ring.open(token, ttl),
        };
        match case["expect"].as_str() {
            Some(plain) => {
                assert_eq!(got.unwrap(), plain.as_bytes(), "{name}");
                opened += 1;
            }
            None => {
                assert_eq!(got, Err(CryptoError::InvalidToken), "{name}");
                refused += 1;
            }
        }
    }
    // the vector must exercise both outcomes, and plenty of them
    assert!(
        opened >= 30 && refused >= 50,
        "{opened} opened, {refused} refused"
    );
}

#[test]
fn a_token_sealed_here_is_the_token_python_seals() {
    let v = vector();
    let t0 = v["t0"].as_u64().unwrap();
    let ring = FernetRing::parse(v["keys"]["k1"].as_str().unwrap()).unwrap();
    let mut matched = 0;
    for case in v["cases"].as_array().unwrap() {
        let name = case["name"].as_str().unwrap();
        if !name.ends_with("sealed with the current key, ring of one") {
            continue;
        }
        let plain = case["expect"].as_str().unwrap();
        assert_eq!(
            ring.seal_at(plain.as_bytes(), t0, iv()),
            case["token"].as_str().unwrap(),
            "{name}"
        );
        matched += 1;
    }
    assert_eq!(matched, v["plaintexts"].as_object().unwrap().len());
}

#[test]
fn rotation_a_value_sealed_with_the_previous_key_opens_with_the_ring() {
    let v = vector();
    let (k1, k2) = (
        v["keys"]["k1"].as_str().unwrap(),
        v["keys"]["k2"].as_str().unwrap(),
    );
    let old = FernetRing::parse(k2).unwrap();
    let token = old.seal(b"sealed before the rotation");
    let ring = FernetRing::parse(&format!("{k1},{k2}")).unwrap();
    assert_eq!(
        ring.open(&token, None).unwrap(),
        b"sealed before the rotation"
    );
    assert_eq!(ring.opening_position(&token, None), Some(1));
    assert_eq!(ring.opening_member(&token, None), Some(k2));
    // the ring seals with the first key; the previous key alone cannot open it
    let fresh = ring.seal(b"after");
    assert_eq!(ring.opening_position(&fresh, None), Some(0));
    assert_eq!(ring.opening_member(&fresh, None), Some(k1));
    assert!(old.open(&fresh, None).is_err());
    // the new key alone cannot open what only the old one sealed
    assert!(FernetRing::parse(k1).unwrap().open(&token, None).is_err());
    assert_eq!(ring.member_count(), 2);
    // a token no member opens has no position
    let stranger = FernetRing::parse(v["keys"]["k3"].as_str().unwrap()).unwrap();
    assert_eq!(ring.opening_position(&stranger.seal(b"x"), None), None);
}

#[test]
fn the_time_limit_follows_cryptography_exactly() {
    let v = vector();
    let ring = FernetRing::parse(v["keys"]["k1"].as_str().unwrap()).unwrap();
    let t0 = 1_700_000_000u64;
    let token = ring.seal_at(b"x", t0, iv());
    for (ttl, now, ok) in [
        (60, t0 + 60, true),
        (60, t0 + 61, false),
        (60, t0 - 60, true),
        (60, t0 - 61, false),
        (0, t0, true),
        (0, t0 + 1, false),
        (u64::MAX, t0 + 5, false), // an overflowing limit is a refusal, never a panic
    ] {
        assert_eq!(
            ring.open_at(&token, Some(ttl), now).is_ok(),
            ok,
            "ttl {ttl} now {now}"
        );
    }
    // no limit: any clock
    assert!(ring.open_at(&token, None, 0).is_ok());
    assert!(ring.open_at(&token, None, u64::MAX).is_ok());
}

#[test]
fn wrong_keys_and_unusable_keys() {
    let v = vector();
    let k1 = v["keys"]["k1"].as_str().unwrap();
    let token = FernetRing::parse(k1).unwrap().seal(b"s");
    let other = FernetRing::parse(&generate_key()).unwrap();
    assert_eq!(other.open(&token, None), Err(CryptoError::InvalidToken));
    for bad in [
        "",
        "   ",
        "not a key",
        "AAAA",
        &format!("{k1},AAAA"),
        &format!("{k1},"),
    ] {
        assert!(FernetRing::parse(bad).is_err(), "{bad:?}");
    }
    // a key as an env file writes it
    assert!(FernetRing::parse(&format!("\"{k1}\"")).is_ok());
}

#[test]
fn a_plaintext_that_is_not_text_is_refused_as_text() {
    let ring = FernetRing::parse(&generate_key()).unwrap();
    let token = ring.seal(&[0xff, 0xfe, 0xfd]);
    assert_eq!(ring.open(&token, None).unwrap(), vec![0xff, 0xfe, 0xfd]);
    assert_eq!(ring.open_str(&token, None), Err(CryptoError::InvalidToken));
}

#[test]
fn keys_are_never_printed_and_errors_never_carry_a_value() {
    let v = vector();
    let k1 = v["keys"]["k1"].as_str().unwrap();
    let ring = FernetRing::parse(&format!("{k1},{}", v["keys"]["k2"].as_str().unwrap())).unwrap();
    for shown in [format!("{ring:?}"), format!("{ring:#?}")] {
        assert!(!shown.contains(&k1[..12]), "{shown}");
        assert!(shown.contains("redacted"));
    }
    let err = FernetRing::parse("hunter2-not-a-key")
        .unwrap_err()
        .to_string();
    assert!(!err.contains("hunter2"));
    let token = ring.seal(b"plain");
    let err = ring
        .open(&format!("{token}x"), None)
        .unwrap_err()
        .to_string();
    assert!(!err.contains(&token));
}

#[test]
fn sealed_envelopes_python_wrote_open_and_are_bound_to_their_row() {
    let v = vector();
    let e = &v["envelopes"];
    let ring = FernetRing::parse(e["ring"].as_str().unwrap()).unwrap();
    let args = |name: &str, key: &str| -> (String, String) {
        let a = &e[name][key];
        (
            a[0].as_str().unwrap().to_string(),
            a[1].as_str().unwrap().to_string(),
        )
    };
    let sealed_of = |name: &str| e[name]["sealed"].as_str().unwrap().to_string();
    let plain_of = |name: &str| e[name]["plaintext"].as_str().unwrap().to_string();

    let (w, s) = args("registration", "args");
    assert_eq!(
        sealed::unseal_registration_secret(&ring, &w, &s, Some(&sealed_of("registration")))
            .unwrap(),
        Some(plain_of("registration"))
    );
    let (w2, s2) = args("registration", "wrong_args");
    assert!(
        sealed::unseal_registration_secret(&ring, &w2, &s2, Some(&sealed_of("registration")))
            .is_err()
    );
    assert_eq!(
        sealed::unseal_registration_secret(&ring, &w, &s, None).unwrap(),
        None
    );
    assert_eq!(
        sealed::unseal_registration_secret(&ring, &w, &s, Some("")).unwrap(),
        None
    );
    // a webhook envelope is not a registration secret (no service id in it)
    assert!(
        sealed::unseal_registration_secret(
            &ring,
            &w,
            &s,
            Some(e["registration"]["as_webhook"].as_str().unwrap())
        )
        .is_err()
    );

    let (w, h) = args("webhook_url", "args");
    assert_eq!(
        sealed::unseal_webhook_url(&ring, &w, &h, Some(&sealed_of("webhook_url"))).unwrap(),
        plain_of("webhook_url")
    );
    let (w2, h2) = args("webhook_url", "wrong_args");
    assert!(sealed::unseal_webhook_url(&ring, &w2, &h2, Some(&sealed_of("webhook_url"))).is_err());
    assert!(sealed::unseal_webhook_url(&ring, &w, &h, None).is_err());
    assert!(
        sealed::unseal_webhook_url(
            &ring,
            &w,
            &h,
            Some(e["webhook_url"]["as_totp"].as_str().unwrap())
        )
        .is_err()
    );

    let (u, f) = args("totp_secret", "args");
    assert_eq!(
        sealed::unseal_totp_secret(&ring, &u, &f, Some(&sealed_of("totp_secret"))).unwrap(),
        plain_of("totp_secret")
    );
    let (u2, f2) = args("totp_secret", "wrong_args");
    assert!(sealed::unseal_totp_secret(&ring, &u2, &f2, Some(&sealed_of("totp_secret"))).is_err());
    assert!(
        sealed::unseal_totp_secret(
            &ring,
            &u,
            &f,
            Some(e["totp_secret"]["as_webhook"].as_str().unwrap())
        )
        .is_err()
    );
}

#[test]
fn an_envelope_sealed_here_opens_here_and_is_refused_elsewhere() {
    let ring = FernetRing::parse(&generate_key()).unwrap();
    let token = sealed::seal_registration_secret(&ring, "w1", "s1", "pässword");
    assert_eq!(
        sealed::unseal_registration_secret(&ring, "w1", "s1", Some(&token)).unwrap(),
        Some("pässword".to_string())
    );
    assert!(sealed::unseal_registration_secret(&ring, "w1", "s2", Some(&token)).is_err());
    let other = FernetRing::parse(&generate_key()).unwrap();
    assert!(sealed::unseal_registration_secret(&other, "w1", "s1", Some(&token)).is_err());
}

/// What Rust seals, Python opens: writes the file `golden_crypto.py
/// check-fernet` reads (only when `RUST_SEALED_OUT` is set).
#[test]
fn rust_sealed_values_for_python_to_open() {
    let Ok(out) = std::env::var("RUST_SEALED_OUT") else {
        return;
    };
    let v = vector();
    let t0 = v["t0"].as_u64().unwrap();
    let (k1, k2) = (
        v["keys"]["k1"].as_str().unwrap(),
        v["keys"]["k2"].as_str().unwrap(),
    );
    let mut tokens = Vec::new();
    for (ring_text, label) in [
        (k1.to_string(), "one key"),
        (format!("{k1},{k2}"), "ring of two"),
    ] {
        let ring = FernetRing::parse(&ring_text).unwrap();
        for (name, plain) in v["plaintexts"].as_object().unwrap() {
            let plain = plain.as_str().unwrap();
            tokens.push(json!({
                "name": format!("{label}: {name}"), "ring": ring_text, "plaintext": plain,
                "now": t0, "ttl": null, "iv_hex": hex::encode(iv()),
                "token": ring.seal_at(plain.as_bytes(), t0, iv()),
            }));
            // a fresh one too: real clock and a random IV, opened within a limit
            let now = bc_crypto::fernet::unix_now();
            tokens.push(json!({
                "name": format!("{label}: {name} (fresh)"), "ring": ring_text, "plaintext": plain,
                "now": now, "ttl": 60, "token": ring.seal(plain.as_bytes()),
            }));
        }
    }
    let ring = FernetRing::parse(v["envelopes"]["ring"].as_str().unwrap()).unwrap();
    let a = &v["envelopes"];
    let get = |n: &str, i: usize| a[n]["args"][i].as_str().unwrap().to_string();
    let env = json!({
        "registration": {"args": [get("registration", 0), get("registration", 1)], "plaintext": "rust-secret",
            "sealed": sealed::seal_registration_secret(&ring, &get("registration", 0), &get("registration", 1), "rust-secret")},
        "webhook_url": {"args": [get("webhook_url", 0), get("webhook_url", 1)], "plaintext": "https://hooks.voorbeeld.example/rust",
            "sealed": sealed::seal_webhook_url(&ring, &get("webhook_url", 0), &get("webhook_url", 1), "https://hooks.voorbeeld.example/rust")},
        "totp_secret": {"args": [get("totp_secret", 0), get("totp_secret", 1)], "plaintext": "JBSWY3DPEHPK3PXP",
            "sealed": sealed::seal_totp_secret(&ring, &get("totp_secret", 0), &get("totp_secret", 1), "JBSWY3DPEHPK3PXP")},
    });
    let file = json!({"fernet": tokens, "envelopes": env});
    std::fs::write(format!("{out}.fernet.json"), file.to_string()).unwrap();
}
