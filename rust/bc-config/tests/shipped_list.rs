//! The published-secret digests here equal the Python list. Runs against the
//! repository checkout; without the Python file next to the workspace (a
//! container that holds only `rust/`) there is nothing to compare and the test
//! says so.

use std::path::Path;

#[test]
#[allow(clippy::print_stderr)]
fn digests_equal_the_python_list() {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../common/common/configs/shipped_secrets.py");
    let Ok(source) = std::fs::read_to_string(&path) else {
        eprintln!("shipped_secrets.py not found: comparison skipped");
        return;
    };
    let start = source
        .find("SHIPPED_SECRET_SHA256 = frozenset(")
        .expect("the Python list is still where it was");
    let block = &source[start..];
    let end = block.find("\n)").expect("the list ends");
    let mut python: Vec<String> = block[..end]
        .split('"')
        .filter(|s| s.len() == 64 && s.bytes().all(|b| b.is_ascii_hexdigit()))
        .map(str::to_string)
        .collect();
    let mut rust: Vec<String> = bc_config::secrets::SHIPPED_SECRET_SHA256
        .iter()
        .map(|s| (*s).to_string())
        .collect();
    python.sort();
    rust.sort();
    assert_eq!(rust, python);
}
