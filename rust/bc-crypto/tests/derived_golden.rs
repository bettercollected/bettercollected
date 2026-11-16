#![allow(
    clippy::unwrap_used,
    clippy::many_single_char_names,
    clippy::too_many_lines,
    clippy::similar_names,
    clippy::single_match_else
)]
//! Every HMAC-derived value, identifier and hash: the expected value in each
//! case is what the Python backend's own function returned
//! (`rust/contract/golden_crypto.py derived`). The values Rust derives are
//! written for Python to verify (`check-derived`, `RUST_SEALED_OUT`).

use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use bc_config::secrets::{KeyRing, token_members};
use bc_crypto::identity::IdentityKey;
use bc_crypto::links::{self, Check};
use bc_crypto::prim::{b64url, py_urlsafe_b64decode, sha256_hex, unb64url};
use bc_crypto::signed::{self, AI_NOTICE, OPTION_SHARE, RESPONSE_CURSOR};
use bc_crypto::sigs::{self, BadSignature};
use bc_crypto::{apikey, captcha, drafts, ids, oauth, pyjson, totp};
use serde_json::{Value, json};
use sha2::Digest;

fn v() -> Value {
    serde_json::from_str(include_str!("golden/derived_vector.json")).unwrap()
}

fn s(value: &Value) -> &str {
    value.as_str().unwrap()
}

fn jwt_ring(text: &str) -> KeyRing {
    KeyRing::from_members(token_members(Some(text)))
}

fn bytes(value: &Value) -> Vec<u8> {
    STANDARD.decode(s(value)).unwrap()
}

fn strs(value: &Value) -> Vec<String> {
    value
        .as_array()
        .unwrap()
        .iter()
        .map(|x| s(x).to_string())
        .collect()
}

fn refs(items: &[String]) -> Vec<&str> {
    items.iter().map(String::as_str).collect()
}

fn ids4(value: &Value) -> [String; 4] {
    let list = strs(value);
    [
        list[0].clone(),
        list[1].clone(),
        list[2].clone(),
        list[3].clone(),
    ]
}

fn check_name(check: Check) -> &'static str {
    match check {
        Check::Valid => "valid",
        Check::Expired => "expired",
        Check::Invalid => "invalid",
    }
}

#[test]
fn signed_tokens_open_as_python_decides() {
    let v = v();
    let (mut opened, mut refused) = (0, 0);
    for case in v["signed"].as_array().unwrap() {
        let (purpose, max) = match s(&case["purpose"]) {
            "cursor" => (RESPONSE_CURSOR, signed::MAX_CURSOR_LENGTH),
            "notice" => (AI_NOTICE, signed::MAX_NOTICE_LENGTH),
            _ => (OPTION_SHARE, signed::MAX_OPTION_SHARE_LENGTH),
        };
        let keys = signed::keys(&jwt_ring(s(&case["ring"])), purpose);
        let got = signed::open(
            &keys,
            purpose,
            s(&case["token"]),
            case["suffix"].as_str(),
            max,
        );
        let name = format!("{} {}", case["purpose"], case["name"]);
        match case["expect_claims"].as_object() {
            Some(claims) => {
                assert_eq!(got.unwrap(), Value::Object(claims.clone()), "{name}");
                opened += 1;
            }
            None => {
                assert!(got.is_none(), "{name}");
                refused += 1;
            }
        }
    }
    assert!(opened >= 6 && refused >= 20, "{opened} {refused}");
}

#[test]
fn a_token_with_no_key_or_too_long_is_refused_and_nothing_is_issued() {
    let none = signed::keys(&KeyRing::from_members(vec![]), RESPONSE_CURSOR);
    assert!(none.is_empty());
    assert!(signed::issue(&none, RESPONSE_CURSOR, &json!({"a": 1}), None).is_none());
    let ring = jwt_ring(&"k".repeat(40));
    let keys = signed::keys(&ring, AI_NOTICE);
    let token = signed::issue(&keys, AI_NOTICE, &json!({"a": 1}), None).unwrap();
    assert!(signed::open(&keys, AI_NOTICE, &token, None, token.len()).is_some());
    assert!(signed::open(&keys, AI_NOTICE, &token, None, token.len() - 1).is_none());
    // a token of one purpose is not another's (different label and version)
    assert!(
        signed::open(
            &signed::keys(&ring, OPTION_SHARE),
            OPTION_SHARE,
            &token,
            None,
            4096
        )
        .is_none()
    );
    assert!(signed::within_window(1000, 1000, 10, 5));
    assert!(signed::within_window(1005, 1000, 10, 5));
    assert!(!signed::within_window(1006, 1000, 10, 5));
    assert!(signed::within_window(990, 1000, 10, 5));
    assert!(!signed::within_window(989, 1000, 10, 5));
}

#[test]
fn captcha_values_match_python() {
    let v = v();
    let c = &v["captcha"];
    let ring = jwt_ring(s(&c["keys_ring"]));
    let keys = captcha::keys(&ring);
    for proof in c["proofs"].as_array().unwrap() {
        let name = s(&proof["name"]);
        let (payload, signature, counters) = captcha::split_header(s(&proof["header"])).unwrap();
        let position = captcha::signing_key_position(&keys, payload, signature).unwrap();
        assert_eq!(position, usize::from(name.contains("previous")), "{name}");
        let tag = captcha::ip_tag(
            &keys[position],
            proof["day"].as_i64().unwrap(),
            s(&proof["client"]),
        );
        assert_eq!(tag, s(&proof["tag"]), "{name}");
        let solved = format!("{payload}.{signature}");
        assert!(
            captcha::proof_solves(&solved, counters, proof["bits"].as_i64().unwrap()),
            "{name}"
        );
        // one more bit of difficulty than was solved for is (almost surely) not met
        assert!(!captcha::proof_solves(&solved, counters, 40), "{name}");
        assert!(!captcha::proof_solves(&solved, "1,2,3", 14));
        assert_eq!(
            captcha::spent_nonce_id(s(&proof["nonce"])),
            s(&proof["spent_id"])
        );
        assert!(captcha::signing_key_position(&keys, &format!("{payload}x"), signature).is_none());
    }
    for case in c["spent"].as_array().unwrap() {
        assert_eq!(
            captcha::spent_nonce_id(s(&case["nonce"])),
            s(&case["expect"])
        );
    }
    for case in c["tags"].as_array().unwrap() {
        let tag = captcha::ip_tag(&keys[0], case["day"].as_i64().unwrap(), s(&case["client"]));
        assert_eq!(tag, s(&case["expect"]));
    }
    for case in c["days"].as_array().unwrap() {
        assert_eq!(
            captcha::day_number(case["unix"].as_i64().unwrap()),
            case["expect"].as_i64().unwrap()
        );
    }
    for case in c["pow"].as_array().unwrap() {
        let digest = sha2::Sha256::digest(
            format!(
                "{}:{}:{}",
                s(&case["solved"]),
                case["index"],
                s(&case["counter"])
            )
            .as_bytes(),
        );
        assert_eq!(
            i64::from(captcha::leading_zero_bits(&digest)),
            case["zero_bits"].as_i64().unwrap()
        );
    }
    assert_eq!(captcha::leading_zero_bits(&[0, 0, 0x10]), 19);
    assert_eq!(captcha::leading_zero_bits(&[0; 4]), 32);
    // malformed headers
    for bad in ["", "a.b", "a.b.c.d", &"x".repeat(1100), "é.b.c"] {
        assert!(captcha::split_header(bad).is_none(), "{bad:?}");
    }
    // the work is verified: what solve() finds proof_solves() accepts
    let challenge = captcha::sign_payload(&keys[0], r#"{"v":1}"#);
    let counters = captcha::solve(&challenge, 14);
    let list = counters
        .iter()
        .map(u64::to_string)
        .collect::<Vec<_>>()
        .join(",");
    assert!(captcha::proof_solves(&challenge, &list, 14));
}

#[test]
fn links_and_run_tokens_match_python() {
    let v = v();
    let l = &v["links"];
    for case in l["export"].as_array().unwrap() {
        let keys = links::export_keys(&jwt_ring(s(&case["ring"])));
        let got = links::check_export_link(
            &keys,
            s(&case["token"]),
            ids4(&case["ids"]).each_ref().map(String::as_str),
            case["now"].as_f64().unwrap(),
        );
        assert_eq!(check_name(got), s(&case["expect"]), "{}", case["name"]);
    }
    let identity = IdentityKey::parse(s(&l["identity_key"])).unwrap();
    let key = links::run_token_key(identity.bytes());
    for case in l["run"].as_array().unwrap() {
        let got = links::check_run_token(
            &key,
            s(&case["token"]),
            ids4(&case["ids"]).each_ref().map(String::as_str),
            case["now"].as_f64().unwrap(),
        );
        assert_eq!(check_name(got), s(&case["expect"]), "{}", case["name"]);
    }
    let lock = strs(&l["run_lock"]["ids"]);
    assert_eq!(
        links::run_lock(&lock[0], &lock[1], &lock[2]),
        s(&l["run_lock"]["expect"])
    );
    // issue and check agree with each other, on the edges
    let ring = jwt_ring(&"q".repeat(40));
    let keys = links::export_keys(&ring);
    let ids = ["e", "w", "f", "u"];
    let token = links::issue_export_link(&keys, ids, 1000.0).unwrap();
    assert_eq!(
        links::check_export_link(&keys, &token, ids, 1300.0),
        Check::Valid
    );
    assert_eq!(
        links::check_export_link(&keys, &token, ids, 1300.5),
        Check::Expired
    );
    assert!(links::issue_export_link(&[], ids, 1.0).is_none());
}

#[test]
fn respondent_identity_matches_python() {
    let v = v();
    let i = &v["identity"];
    let key = IdentityKey::parse(s(&i["key"])).unwrap();
    assert_eq!(key.check_value(), s(&i["check_value"]));
    for row in i["rows"].as_array().unwrap() {
        assert_eq!(
            bc_crypto::identity::md5_hex(s(&row["email"])),
            s(&row["md5"])
        );
        assert_eq!(key.identity_of(s(&row["email"])), s(&row["identity"]));
    }
    let legacy = &i["legacy"];
    assert_eq!(
        key.convert_legacy(s(&legacy["md5"])),
        s(&legacy["converted"])
    );
    assert_eq!(
        key.convert_legacy(s(&legacy["v2_unchanged"])),
        s(&legacy["v2_unchanged"])
    );
    for case in i["decode"].as_array().unwrap() {
        let got = IdentityKey::parse(s(&case["text"]));
        let name = s(&case["name"]);
        match case["expect"].as_str() {
            Some(hex_bytes) => assert_eq!(hex::encode(got.unwrap().bytes()), hex_bytes, "{name}"),
            // a key Python's start-up check calls weak decodes here (the check
            // is not repeated); every other refusal is a refusal here too
            None if name.starts_with("weak") => assert!(got.is_ok(), "{name}"),
            None => assert!(got.is_err(), "{name}"),
        }
    }
    for case in i["matches"].as_array().unwrap() {
        assert_eq!(
            key.matches(s(&case["stored"]), s(&case["email"])),
            case["expect"].as_bool().unwrap()
        );
    }
    assert!(!format!("{key:?}").contains(&s(&i["key"])[..10]));
}

#[test]
fn draft_secrets_and_addresses_match_python() {
    let v = v();
    let d = &v["drafts"];
    let keys = drafts::DraftKeys::new(s(&d["ring"]));
    for case in d["hash"].as_array().unwrap() {
        let got = keys.matches(
            s(&case["purpose"]),
            s(&case["draft_id"]),
            s(&case["secret"]),
            case["stored"].as_str(),
        );
        assert_eq!(
            got,
            case["expect_matches"].as_bool().unwrap(),
            "{}",
            case["name"]
        );
    }
    for case in d["hash_values"].as_array().unwrap() {
        assert_eq!(
            keys.hash_secret(
                s(&case["purpose"]),
                s(&case["draft_id"]),
                s(&case["secret"])
            ),
            s(&case["expect"])
        );
    }
    let single = &d["single_secret"];
    assert_eq!(
        drafts::DraftKeys::new(s(&single["secret"])).hash_secret(
            drafts::TOKEN,
            "6a00000000000000000000aa",
            "s"
        ),
        s(&single["expect"])
    );
    assert_eq!(
        drafts::DraftKeys::new("").hash_secret(drafts::TOKEN, "6a00000000000000000000aa", "s"),
        s(&d["empty_secret"]["expect"])
    );
    let form = "6a0000000000000000000002";
    for case in d["address"].as_array().unwrap() {
        let address = s(&case["address"]);
        let normalised = drafts::normalised_ascii_address(address);
        if case["ascii"].as_bool().unwrap() {
            let normalised = normalised.unwrap();
            assert_eq!(normalised, s(&case["normalised"]), "{address:?}");
            assert_eq!(keys.address_key(form, &normalised), s(&case["key"]));
            assert_eq!(keys.address_keys(form, &normalised), strs(&case["keys"]));
        } else {
            // Unicode normalisation is not reproduced: refused, never guessed
            assert!(normalised.is_none(), "{address:?}");
        }
    }
    for case in d["split"].as_array().unwrap() {
        let got = drafts::split(s(&case["value"]));
        match case["expect"].as_array() {
            Some(pair) => assert_eq!(got, Some((s(&pair[0]), s(&pair[1])))),
            None => assert!(got.is_none(), "{}", case["value"]),
        }
    }
    // request input with a multi-byte character at any offset never panics
    let id = "a".repeat(24);
    let tail = "b".repeat(43);
    let good = format!("{id}.{tail}");
    assert!(drafts::split(&good).is_some());
    let mut shapes = vec![
        format!("{}é{}", "a".repeat(23), "b".repeat(43)),
        format!("{}é{}", "a".repeat(22), "b".repeat(44)),
        format!("{}é.{}", "a".repeat(23), "b".repeat(42)),
        format!("{id}é{}", "b".repeat(42)),
        format!("{id}.{}é", "b".repeat(41)),
        format!("é{}", "a".repeat(67)),
        "é".repeat(34),
        "\u{1f600}".repeat(17),
        String::new(),
        id.clone(),
        format!("{id}."),
        format!("{id}.{}", "b".repeat(42)),
        format!("{id}.{}", "b".repeat(44)),
    ];
    for offset in 0..good.len() {
        let mut chars: Vec<char> = good.chars().collect();
        chars[offset] = 'é';
        shapes.push(chars.into_iter().collect());
    }
    for shape in &shapes {
        assert!(drafts::split(shape).is_none(), "{shape:?}");
    }
    let secret = drafts::new_secret();
    assert_eq!(secret.len(), 43);
    assert!(drafts::split(&drafts::compose("6a00000000000000000000aa", &secret)).is_some());
    assert_ne!(secret, drafts::new_secret());
}

#[test]
fn counters_and_option_ids_match_python() {
    let v = v();
    for case in v["counters"]["rate"].as_array().unwrap() {
        let key = ids::rate_limit_key(&jwt_ring(s(&case["ring"])));
        assert_eq!(
            ids::rate_limit_counter_id(
                &key,
                s(&case["scope"]),
                s(&case["client"]),
                case["window"].as_i64().unwrap()
            ),
            s(&case["expect"])
        );
    }
    for case in v["counters"]["option"].as_array().unwrap() {
        let keys = ids::option_id_keys(&jwt_ring(s(&case["ring"])));
        let got: Vec<String> = keys
            .iter()
            .map(|k| {
                ids::answer_option_id(
                    k,
                    s(&case["workspace"]),
                    s(&case["form"]),
                    s(&case["question"]),
                    s(&case["label"]),
                )
            })
            .collect();
        assert_eq!(got, strs(&case["expect"]));
    }
    for case in v["counters"]["shape"].as_array().unwrap() {
        assert_eq!(
            ids::is_source_id(s(&case["value"])),
            case["expect"].as_bool().unwrap()
        );
    }
    assert!(ids::is_source_id(&ids::new_item_id()));
}

#[test]
fn request_signatures_match_python() {
    let v = v();
    let sg = &v["signatures"];
    for case in sg["webhook"].as_array().unwrap() {
        let body = bytes(&case["body_b64"]);
        let signature = sigs::webhook_sign(
            s(&case["secret"]),
            case["timestamp"].as_i64().unwrap(),
            &body,
        );
        assert_eq!(signature, s(&case["expect"]));
        assert!(sigs::webhook_verify(
            s(&case["secret"]),
            case["timestamp"].as_i64().unwrap(),
            &body,
            &signature
        ));
        assert!(!sigs::webhook_verify(
            "other",
            case["timestamp"].as_i64().unwrap(),
            &body,
            &signature
        ));
        assert!(!sigs::webhook_verify(
            s(&case["secret"]),
            case["timestamp"].as_i64().unwrap(),
            &body,
            ""
        ));
    }
    for case in sg["scim"].as_array().unwrap() {
        let got = sigs::scim_verify(
            case["header"].as_str(),
            &bytes(&case["body_b64"]),
            s(&case["secret"]),
            case["tolerance"].as_i64().unwrap(),
            case["now"].as_f64().unwrap(),
        );
        let name = s(&case["name"]);
        if let Some(ok) = case["expect"].get("ok") {
            assert_eq!(got, Ok(ok.as_i64().unwrap()), "{name}");
        } else {
            let want = match s(&case["expect"]["error"]) {
                "missing" => BadSignature::Missing,
                "malformed" => BadSignature::Malformed,
                "expired" => BadSignature::Expired,
                "no_secret" => BadSignature::NoSecret,
                _ => BadSignature::Mismatch,
            };
            assert_eq!(got, Err(want), "{name}");
        }
    }
}

#[test]
fn oauth_nonces_and_api_keys_match_python() {
    let v = v();
    let o = &v["oauth"];
    for case in o["pkce"].as_array().unwrap() {
        let verifier = oauth::pkce_code_verifier(s(&case["member"]), s(&case["state"]));
        assert_eq!(verifier, s(&case["verifier"]));
        assert_eq!(verifier.len(), 43);
        assert_eq!(oauth::pkce_code_challenge(&verifier), s(&case["challenge"]));
    }
    // the exchange derives with the member that opened the state
    let ring = bc_crypto::fernet::FernetRing::parse(s(&o["pkce_default"]["ring"])).unwrap();
    let token = ring.seal(b"state");
    let member = ring
        .opening_member(&token, Some(oauth::STATE_MAX_AGE_SECONDS))
        .unwrap();
    assert_eq!(
        oauth::pkce_code_verifier(member, "s1"),
        s(&o["pkce_default"]["verifier"])
    );
    assert_eq!(
        o["state_max_age"].as_u64().unwrap(),
        oauth::STATE_MAX_AGE_SECONDS
    );
    for (case, sso) in o["nonce"]
        .as_array()
        .unwrap()
        .iter()
        .zip(o["sso"].as_array().unwrap())
    {
        assert_eq!(
            oauth::integration_nonce_hash(s(&case["nonce"])),
            s(&case["expect"])
        );
        assert_eq!(oauth::sso_nonce_hash(s(&sso["nonce"])), s(&sso["expect"]));
        // an absent nonce hashes as the empty text (Python's `nonce_hash(None)`): an
        // input to a hash function, not a nonce in use
        assert_eq!(oauth::sso_nonce_hash(""), s(&sso["none_hash"]));
        let nonce = s(&sso["nonce"]);
        assert_eq!(
            oauth::sso_nonce_matches(nonce, s(&sso["expect"])),
            !nonce.is_empty()
        );
        assert!(!oauth::sso_nonce_matches(
            &bc_crypto::random::token_urlsafe(32),
            s(&sso["expect"])
        ));
    }
    for case in o["api"].as_array().unwrap() {
        assert_eq!(apikey::hash(s(&case["token"])), s(&case["hash"]));
    }
    let key = apikey::generate();
    assert!(key.token.starts_with("bc_") && key.token.len() == 67);
    assert!(
        key.token[3..]
            .bytes()
            .all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
    );
    assert_eq!(key.prefix, key.token[..11]);
    assert_eq!(key.key_hash, apikey::hash(&key.token));
    assert!(apikey::has_prefix(&key.token) && !apikey::has_prefix("sk_x"));
    assert!(!format!("{key:?}").contains(&key.token));
}

#[test]
fn totp_and_recovery_codes_match_python() {
    let v = v();
    let t = &v["totp"];
    for case in t["hotp"].as_array().unwrap() {
        let key = hex::decode(s(&case["key_hex"])).unwrap();
        assert_eq!(
            totp::hotp(&key, case["counter"].as_u64().unwrap()),
            s(&case["expect"])
        );
    }
    for case in t["verify"].as_array().unwrap() {
        let got = totp::verify(
            s(&case["secret"]),
            s(&case["code"]),
            case["now"].as_f64().unwrap(),
            totp::DRIFT_STEPS,
        );
        assert_eq!(got, case["expect"].as_u64(), "{case}");
    }
    for case in t["decode"].as_array().unwrap() {
        let got = totp::decode_secret(s(&case["text"])).map(hex::encode);
        assert_eq!(got.as_deref(), case["expect"].as_str(), "{}", case["text"]);
    }
    for case in t["replay"].as_array().unwrap() {
        assert_eq!(
            totp::next_last_used_step(case["last"].as_u64(), case["matched"].as_u64().unwrap()),
            case["expect"].as_u64()
        );
    }
    for case in t["recovery"].as_array().unwrap() {
        let code = s(&case["code"]);
        assert_eq!(totp::normalise_recovery_code(code), s(&case["normalised"]));
        assert_eq!(
            totp::recovery_code_well_formed(code),
            case["well_formed"].as_bool().unwrap(),
            "{code:?}"
        );
        assert_eq!(
            totp::hash_recovery_code("6a0000000000000000000003", code),
            s(&case["hash"])
        );
    }
    let generated = totp::generate_recovery_code();
    assert!(totp::recovery_code_well_formed(&generated) && generated.len() == 19);
    let secret = totp::generate_secret();
    assert_eq!(secret.len(), 32);
    assert_eq!(totp::decode_secret(&secret).unwrap().len(), 20);
    assert!(
        totp::verify(
            &secret,
            &totp::code_at(&secret, 1_700_000_000.0).unwrap(),
            1_700_000_000.0,
            1
        )
        .is_some()
    );
}

#[test]
fn hashes_and_lock_keys_match_python() {
    let v = v();
    let i = &v["ids"];
    for case in i["captcha_count"].as_array().unwrap() {
        let k = strs(&case["key"]);
        assert_eq!(
            ids::captcha_count_id([&k[0], &k[1], &k[2], &k[3], &k[4]]),
            s(&case["expect"])
        );
    }
    for case in i["lock"].as_array().unwrap() {
        let parts = strs(&case["parts"]);
        assert_eq!(
            ids::advisory_lock_key(&refs(&parts)),
            case["expect"].as_i64().unwrap(),
            "{parts:?}"
        );
    }
    let (mut export, mut import) = (0, 0);
    for case in i["workspace_lock"].as_array().unwrap() {
        let prefix = if s(&case["kind"]) == "export" {
            export += 1;
            "response-export|"
        } else {
            import += 1;
            "response-import|"
        };
        assert_eq!(
            ids::workspace_lock_key(prefix, s(&case["workspace"])),
            case["expect"].as_i64().unwrap()
        );
    }
    assert_eq!((export, import), (3, 3));
    for case in i["request_hash"].as_array().unwrap() {
        let extra = strs(&case["extra"]);
        assert_eq!(
            ids::request_hash(
                s(&case["method"]),
                s(&case["path"]),
                &bytes(&case["body_b64"]),
                &refs(&extra)
            ),
            s(&case["expect"]),
            "{}",
            String::from_utf8_lossy(&bytes(&case["body_b64"]))
        );
    }
    for case in i["record_id"].as_array().unwrap() {
        assert_eq!(
            ids::idempotency_record_id(s(&case["key_id"]), s(&case["key"])),
            s(&case["expect"])
        );
    }
    for case in i["builtin_target"].as_array().unwrap() {
        let a = strs(&case["args"]);
        assert_eq!(
            ids::builtin_target_id(&a[0], &a[1], &a[2]),
            s(&case["expect"])
        );
    }
    for case in i["custom_domain_key"].as_array().unwrap() {
        let a = strs(&case["args"]);
        assert_eq!(
            ids::custom_domain_idempotency_key(&a[0], &a[1], &a[2]),
            s(&case["expect"])
        );
    }
    for case in i["spec_hash"].as_array().unwrap() {
        assert_eq!(
            ids::canonical_hash(&case["doc"], 16),
            s(&case["expect"]),
            "{}",
            case["doc"]
        );
    }
    for case in i["etag"].as_array().unwrap() {
        assert_eq!(
            ids::form_etag(case["updated_ms"].as_u64().unwrap(), &case["doc"]),
            s(&case["expect"])
        );
    }
    for case in i["policy_fingerprint"].as_array().unwrap() {
        let visible = strs(&case["visible"]);
        assert_eq!(
            ids::visible_fingerprint(&refs(&visible)),
            s(&case["expect"])
        );
    }
    for case in i["scim_event"].as_array().unwrap() {
        assert_eq!(
            ids::scim_event_key(
                s(&case["directory"]),
                &pyjson::Json::from_value(&case["event"]),
                case["timestamp_ms"].as_i64().unwrap(),
                case["index"].as_i64().unwrap()
            ),
            s(&case["expect"])
        );
    }
    for case in i["scim_event_bodies"].as_array().unwrap() {
        let event = pyjson::parse(&bytes(&case["body_b64"])).unwrap();
        assert_eq!(
            ids::scim_event_key(
                s(&i["scim_event"][0]["directory"]),
                &event,
                1_700_000_000_000,
                2
            ),
            s(&case["expect"])
        );
    }
    for case in i["of_component"].as_array().unwrap() {
        assert_eq!(
            ids::open_formulieren_component_id(s(&case["seed"]), s(&case["key"])),
            s(&case["expect"])
        );
    }
}

#[test]
fn python_json_text_is_reproduced() {
    for case in v()["pyjson"].as_array().unwrap() {
        let value: Value = serde_json::from_str(s(&case["text"])).unwrap();
        assert_eq!(
            pyjson::dumps(&value, pyjson::DEFAULT),
            s(&case["default"]),
            "{}",
            case["text"]
        );
        assert_eq!(
            pyjson::dumps(&value, pyjson::COMPACT),
            s(&case["compact"]),
            "{}",
            case["text"]
        );
        assert_eq!(
            pyjson::dumps(&value, pyjson::CANONICAL),
            s(&case["canonical"]),
            "{}",
            case["text"]
        );
    }
    for (f, repr) in [
        (0.1, "0.1"),
        (1e16, "1e+16"),
        (1.5e-7, "1.5e-07"),
        (100.0, "100.0"),
        (1e15, "1000000000000000.0"),
        (0.0001, "0.0001"),
        (0.00001, "1e-05"),
        (-0.0, "-0.0"),
        (123_456_789.123_456_79, "123456789.12345679"),
    ] {
        assert_eq!(pyjson::float_repr(f), repr);
    }
}

#[test]
fn json_bodies_are_read_and_written_as_python_does() {
    let (mut read, mut refused, mut declined) = (0, 0, 0);
    for case in v()["loads"].as_array().unwrap() {
        let body = bytes(&case["body_b64"]);
        let got = pyjson::parse(&body).map(|j| j.canonical());
        let shown = String::from_utf8_lossy(&body[..body.len().min(60)]).to_string();
        if case["rust_declines"].as_bool().unwrap() {
            // Python reads it (UTF-16/32, nesting beyond 500); the caller hashes the bytes
            assert_eq!(got, None, "{shown}");
            declined += 1;
        } else {
            assert_eq!(got.as_deref(), case["expect"].as_str(), "{shown}");
            if got.is_some() {
                read += 1;
            } else {
                refused += 1;
            }
        }
    }
    assert!(
        read >= 50 && refused >= 25 && declined >= 3,
        "{read} {refused} {declined}"
    );

    // two integers beyond 64 bits are two values, and so are their hashes
    let a = ids::request_hash("POST", "/x", b"18446744073709551616", &[]);
    let b = ids::request_hash("POST", "/x", b"18446744073709551617", &[]);
    assert_ne!(a, b);
    let a = ids::request_hash("POST", "/x", br#"{"id":18446744073709551616}"#, &[]);
    let b = ids::request_hash("POST", "/x", br#"{ "id": 18446744073709551617 }"#, &[]);
    assert_ne!(a, b);
    // the same value in another layout is one request; -0 is 0 but -0.0 is not 0.0
    assert_eq!(
        ids::request_hash("POST", "/x", br#"{"b":-0,"a":1}"#, &[]),
        ids::request_hash("POST", "/x", br#" {"a": 1, "b": 0} "#, &[])
    );
    assert_ne!(
        ids::request_hash("POST", "/x", b"-0.0", &[]),
        ids::request_hash("POST", "/x", b"0.0", &[])
    );
    // nesting beyond what the backend reads is hashed as bytes, never an overflow
    let deep = format!("{}{}", "[".repeat(5000), "]".repeat(5000));
    assert!(pyjson::parse(deep.as_bytes()).is_none());
    assert_eq!(pyjson::parse(b"[[1]]").unwrap().canonical(), "[[1]]");
    assert!(
        pyjson::parse(br#"{"a":[1,{"b":null}]}"#)
            .unwrap()
            .get("a")
            .is_some()
    );
}

/// How long a thing takes, for the bounds below.
fn timed<T>(work: impl FnOnce() -> T) -> (T, std::time::Duration) {
    let start = std::time::Instant::now();
    let out = work();
    (out, start.elapsed())
}

/// Bound for the many-keys bodies, chosen from measurements in the unoptimised
/// test profile (the profile CI runs): 80,000 distinct keys read in about 0.26 s
/// with the hash index and in about 44 s when the keys seen so far are scanned
/// (3.2 billion comparisons; the `--nocapture` lines print the figure). Four
/// seconds is 15 times the linear time, so a loaded shared runner that is several
/// times slower still passes, and a tenth of the quadratic time, so the scan
/// cannot.
const MANY_KEYS_BOUND: std::time::Duration = std::time::Duration::from_secs(4);

#[test]
fn a_body_with_many_keys_is_read_in_linear_time() {
    // 80,000 distinct keys (about 850 KB)
    let distinct = {
        let members: Vec<String> = (0..80_000).map(|i| format!("\"key{i}\":{i}")).collect();
        format!("{{{}}}", members.join(","))
    };
    let (hash, took) = timed(|| ids::request_hash("POST", "/x", distinct.as_bytes(), &[]));
    eprintln!("80000 distinct keys: {took:?}");
    assert!(took < MANY_KEYS_BOUND, "{took:?}");
    assert_eq!(hash.len(), 64);
    let parsed = pyjson::parse(distinct.as_bytes()).unwrap();
    assert_eq!(
        parsed
            .get("key79999")
            .map(pyjson::Json::canonical)
            .as_deref(),
        Some("79999")
    );

    // 80,000 repeats of one key: first place, last value
    let repeats = {
        let members: Vec<String> = (0..80_000).map(|i| format!("\"k\":{i}")).collect();
        format!("{{\"first\":0,{}}}", members.join(","))
    };
    let (parsed, took) = timed(|| pyjson::parse(repeats.as_bytes()).unwrap());
    eprintln!("80000 repeats of one key: {took:?}");
    assert!(took < MANY_KEYS_BOUND, "{took:?}");
    assert_eq!(parsed.canonical(), r#"{"first":0,"k":79999}"#);
    assert_eq!(parsed.dumps(pyjson::COMPACT), r#"{"first":0,"k":79999}"#);

    // distinct keys, each repeated once: 40,000 keys twice (80,000 members)
    let pairs = {
        let mut members: Vec<String> = (0..40_000).map(|i| format!("\"p{i}\":1")).collect();
        members.extend((0..40_000).map(|i| format!("\"p{i}\":2")));
        format!("{{{}}}", members.join(","))
    };
    let (parsed, took) = timed(|| pyjson::parse(pairs.as_bytes()).unwrap());
    eprintln!("40000 keys twice: {took:?}");
    assert!(took < MANY_KEYS_BOUND, "{took:?}");
    assert_eq!(
        parsed.get("p39999").map(pyjson::Json::canonical).as_deref(),
        Some("2")
    );

    // a long array and a long string are linear too
    let array = format!("[{}]", vec!["1"; 200_000].join(","));
    let (_, took) = timed(|| pyjson::parse(array.as_bytes()).unwrap().canonical());
    assert!(took < MANY_KEYS_BOUND, "{took:?}");
    let long = format!("\"{}\"", "é".repeat(400_000));
    let (_, took) = timed(|| pyjson::parse(long.as_bytes()).unwrap().canonical());
    assert!(took < MANY_KEYS_BOUND, "{took:?}");
}

#[test]
fn nesting_is_read_to_the_depth_the_running_backend_accepts() {
    // measured on the deployed interpreter (Python 3.11.12) by `json_depth_probe.py`
    assert_eq!(pyjson::MAX_DEPTH, 982);
    assert_eq!(pyjson::MAX_DEPTH_EDITOR_OPS, 983);
    let d = &v()["depth"];
    assert_eq!(
        d["limits"]["public"].as_u64().unwrap(),
        pyjson::MAX_DEPTH as u64
    );
    assert_eq!(
        d["limits"]["editor"].as_u64().unwrap(),
        pyjson::MAX_DEPTH_EDITOR_OPS as u64
    );
    let mut boundary = 0;
    for case in d["cases"].as_array().unwrap() {
        let body = bytes(&case["body_b64"]);
        let name = format!("{} {}", case["kind"], case["depth"]);
        let public = pyjson::parse(&body);
        let editor = pyjson::parse_limited(&body, pyjson::MAX_DEPTH_EDITOR_OPS);
        assert_eq!(
            public.is_some(),
            case["public_accepts"].as_bool().unwrap(),
            "{name}"
        );
        assert_eq!(
            editor.is_some(),
            case["editor_accepts"].as_bool().unwrap(),
            "{name}"
        );
        if let (Some(parsed), Some(canonical)) = (&public, case["canonical"].as_str()) {
            assert_eq!(parsed.canonical(), canonical, "{name}");
        }
        if matches!(case["depth"].as_u64(), Some(982 | 983)) {
            boundary += 1;
        }
    }
    assert_eq!(boundary, 6);
    // a refused body is hashed as bytes, an accepted one by value
    let deep = format!("{}{}", "[".repeat(983), "]".repeat(983));
    assert_ne!(
        ids::request_hash("POST", "/x", deep.as_bytes(), &[]),
        ids::request_hash(
            "POST",
            "/x",
            format!("{}{}", "[".repeat(983), " ]".repeat(983)).as_bytes(),
            &[]
        )
    );
    assert_eq!(
        ids::request_hash_limited("POST", "/x", deep.as_bytes(), &[], 983),
        ids::request_hash_limited(
            "POST",
            "/x",
            format!("{}{}", "[".repeat(983), " ]".repeat(983)).as_bytes(),
            &[],
            983
        )
    );
}

#[test]
fn reading_writing_and_dropping_never_recurse() {
    // far beyond any limit, on this test's small stack: the reader stops at the
    // limit without recursing, and a value as deep as a raised limit is written
    // and dropped without recursing either
    let nested = |n: usize| format!("{}{}", "[".repeat(n), "]".repeat(n));
    let objects = |n: usize| format!("{}1{}", "{\"a\":".repeat(n), "}".repeat(n));
    assert!(pyjson::parse("[".repeat(1_000_000).as_bytes()).is_none());
    assert!(pyjson::parse(nested(1_000_000).as_bytes()).is_none());
    for limit in [20_000, 200_000] {
        let at = pyjson::parse_limited(nested(limit).as_bytes(), limit).unwrap();
        assert_eq!(at.canonical(), nested(limit));
        drop(at);
        let at = pyjson::parse_limited(objects(limit).as_bytes(), limit).unwrap();
        assert_eq!(at.canonical().len(), objects(limit).len());
        drop(at);
        assert!(pyjson::parse_limited(nested(limit + 1).as_bytes(), limit).is_none());
    }
}

#[test]
fn base64_reading_agrees_with_python_where_python_is_well_defined() {
    for case in v()["b64"].as_array().unwrap() {
        let got = py_urlsafe_b64decode(s(&case["text"])).map(hex::encode);
        assert_eq!(
            got.as_deref(),
            case["python"].as_str(),
            "{}: {}",
            case["name"],
            case["text"]
        );
    }
    // the signed-token reader pads by itself
    assert_eq!(unb64url("YQ").unwrap(), b"a");
    assert_eq!(unb64url("YWJj").unwrap(), b"abc");
    assert!(unb64url("Y").is_none());
    assert_eq!(b64url(&[0xfb, 0xff]), "-_8");
    assert_eq!(
        sha256_hex(b""),
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    );
}

/// What Rust derives, Python verifies (`golden_crypto.py check-derived`;
/// only when `RUST_SEALED_OUT` is set).
#[test]
fn rust_derived_values_for_python_to_verify() {
    let Ok(out) = std::env::var("RUST_SEALED_OUT") else {
        return;
    };
    let v = v();
    let t0 = v["t0"].as_i64().unwrap();
    let (ring_a, ring_b) = (s(&v["jwt"]["a"]), s(&v["jwt"]["b"]));
    let ring_text = format!("{ring_a},{ring_b}");
    let ring = jwt_ring(&ring_text);
    let (ws, form, user) = (
        "6a0000000000000000000001",
        "6a0000000000000000000002",
        "6a0000000000000000000003",
    );

    // cursor, notice, share
    let ckeys = signed::keys(&ring, RESPONSE_CURSOR);
    let cursor = signed::issue(
        &ckeys,
        RESPONSE_CURSOR,
        &json!({"w": ws, "f": form, "s": "created_at", "d": true, "z": 50, "p": 4,
                "t": "2023-11-14T21:13:20.000000+00:00", "r": "6a00000000000000000000ee", "i": t0 * 1000}),
        Some(s(&v["check_fingerprint"])),
    )
    .unwrap();
    let notice = signed::issue(
        &signed::keys(&ring, AI_NOTICE),
        AI_NOTICE,
        &json!({"w": ws, "f": form, "p": "openai", "n": "OpenAI", "e": (t0 - 5) * 1000, "i": t0 * 1000}),
        None,
    )
    .unwrap();
    let share = signed::issue(
        &signed::keys(&ring, OPTION_SHARE),
        OPTION_SHARE,
        &json!({"w": ws, "f": form, "q": ["q-x", "q-y"], "i": t0 * 1000}),
        None,
    )
    .unwrap();

    // captcha
    let ckeys = captcha::keys(&ring);
    let day = captcha::day_number(t0);
    let claims = json!({"v": 1, "alg": "sha256-lz", "p": "submit", "w": ws, "f": form,
        "n": b64url(&bc_crypto::random::bytes::<16>()), "b": 14, "k": 8, "d": day,
        "t": captcha::ip_tag(&ckeys[0], day, "203.0.113.9"), "e": (t0 + 900) * 1000});
    let challenge = captcha::sign_payload(&ckeys[0], &claims.to_string());
    let counters = captcha::solve(&challenge, 14)
        .iter()
        .map(u64::to_string)
        .collect::<Vec<_>>()
        .join(",");
    let captcha_proof = format!("{challenge}.{counters}");

    // links and identity
    let export_ids = ["6a00000000000000000000e1", ws, form, user];
    #[allow(clippy::cast_precision_loss)]
    let now = t0 as f64;
    let export = links::issue_export_link(&links::export_keys(&ring), export_ids, now).unwrap();
    let identity = IdentityKey::parse(s(&v["identity_key"])).unwrap();
    let run_ids = [
        ws,
        form,
        "6a00000000000000000000a1",
        "6a00000000000000000000f1",
    ];
    let run = links::run_token(&links::run_token_key(identity.bytes()), run_ids, now);

    // drafts
    let keys = drafts::DraftKeys::new(&ring_text);
    let draft_id = "6a00000000000000000000aa";
    let secret = drafts::new_secret();

    // signatures
    let sig_secret = "rust-shared-secret-0123456789";
    let body = br#"{"a":1}"#;

    // totp
    let totp_secret = totp::generate_secret();
    #[allow(clippy::cast_precision_loss)]
    let code = totp::code_at(&totp_secret, t0 as f64).unwrap();
    let recovery = totp::generate_recovery_code();

    let api = apikey::generate();
    let verifier = oauth::pkce_code_verifier(s(&v["fernet"]["a"]), "state-1");
    let doc = json!({"b": [1, 2.5, "é"], "a": null});

    let file = json!({
        "issued": t0, "cursor": cursor, "notice": notice, "share": share,
        "captcha_proof": captcha_proof, "export": export, "export_ids": export_ids,
        "run": run, "run_ids": run_ids,
        "identity": identity.identity_of("rust@voorbeeld.example"),
        "draft": {"id": draft_id, "secret": secret, "hash": keys.hash_secret(drafts::TOKEN, draft_id, &secret),
                  "address": keys.address_key(form, "rust@voorbeeld.example")},
        "secret": sig_secret,
        "webhook": sigs::webhook_sign(sig_secret, 1_700_000_000, body),
        "scim": sigs::scim_sign(sig_secret, body, t0 * 1000),
        "totp_secret": totp_secret, "totp_code": code,
        "recovery": {"code": recovery, "hash": totp::hash_recovery_code(user, &recovery)},
        "recovery_generated": totp::generate_recovery_code(),
        "api": {"token": api.token, "hash": api.key_hash},
        "pkce": {"verifier": verifier, "challenge": oauth::pkce_code_challenge(&verifier)},
        "rate": ids::rate_limit_counter_id(&ids::rate_limit_key(&ring), "s", "c", 7),
        "option": ids::option_id_keys(&ring).iter().map(|k| ids::answer_option_id(k, ws, form, "q", "ja")).collect::<Vec<_>>(),
        "new_item_id": ids::new_item_id(),
        "etag": ids::form_etag(1_700_000_000_000, &doc),
    });
    std::fs::write(format!("{out}.derived.json"), file.to_string()).unwrap();
}
