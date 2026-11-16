//! Python's `json`, for the values whose text is hashed, signed or compared:
//! `json.loads` of a request body ([`parse`]) and `json.dumps` of the result
//! ([`Json::dumps`], [`dumps`]), reproduced so that a Rust and a Python writer
//! produce the same bytes for the same input and, as important, never the same
//! bytes for two inputs Python tells apart.
//!
//! What [`parse`] reads exactly as `json.loads` does:
//!
//! - integers of any size are exact (`18446744073709551616` and `...617` stay
//!   two values) and `-0` is the integer `0`; an integer of more than 4300
//!   digits is refused, as Python 3.11+ refuses it;
//! - a number with a fraction or an exponent is a float, correctly rounded
//!   (`9007199254740993.0` is `9007199254740992.0`, `1e400` is infinity);
//! - `NaN`, `Infinity` and `-Infinity` are accepted;
//! - strings keep lone surrogate escapes (`"\ud800"`), and a high and a low
//!   surrogate escape in a row make one character;
//! - a repeated key keeps its first position with its last value;
//! - the input is UTF-8, a leading byte order mark is skipped.
//!
//! What it refuses where Python reads: a UTF-16 or UTF-32 body. Nesting is
//! limited as the backend limits a request body ([`MAX_DEPTH`], 128 levels; a
//! deeper body never reaches the parser there). A caller
//! that gets `None` hashes the raw bytes, as `request_hash` does when Python's
//! parser raises `ValueError`. Reading, writing and dropping a value never
//! recurse, so a body nested to the limit cannot overflow the stack, and no
//! step is slower than linear in the body (an object with many keys uses a
//! keyed hash index for repeated keys, not a scan).
//!
//! Output is ASCII only (`ensure_ascii`), with either the default separators
//! (`", "`, `": "`) or the compact ones, keys in insertion order or sorted by
//! code point. Floats follow `repr(float)` (shortest round-trip digits, an
//! exponent below 1e-4 and from 1e16 on, `NaN`/`Infinity`).
//!
//! [`dumps`] writes a `serde_json::Value`, whose objects are ordered by key (so
//! `DEFAULT` and `COMPACT` differ from Python for an object written in another
//! order; `CANONICAL` sorts in Python too) and whose integers beyond 64 bits
//! have already become floats: a body is parsed with [`parse`], never with
//! `serde_json`, before it is hashed.

use std::fmt::Write as _;

use serde_json::Value;

#[derive(Clone, Copy, Debug)]
pub struct Options {
    pub sort_keys: bool,
    /// `separators=(",", ":")` when true, Python's default `(", ", ": ")` when false.
    pub compact: bool,
}

/// `json.dumps(value)`.
pub const DEFAULT: Options = Options {
    sort_keys: false,
    compact: false,
};
/// `json.dumps(value, separators=(",", ":"))`.
pub const COMPACT: Options = Options {
    sort_keys: false,
    compact: true,
};
/// `json.dumps(value, sort_keys=True, separators=(",", ":"))`.
pub const CANONICAL: Options = Options {
    sort_keys: true,
    compact: true,
};

/// The deepest nesting [`parse`] reads: `MAX_JSON_DEPTH` of the Python backend
/// (`backend/app/utils/json_depth.py`), the limit its middleware puts on every
/// JSON request body (a deeper one is refused with 422 `body_too_deep` before
/// any route, and so before `request_hash`, reads it; `bc_http::json_depth` is
/// the same rule for the routes Rust serves). A body nested deeper is declined
/// here, and a caller hashes its bytes. Change both limits together.
pub const MAX_DEPTH: usize = 128;
/// Python 3.11+ `int()` refuses a decimal string longer than this.
const MAX_INT_DIGITS: usize = 4300;

/// A Python JSON value. A string is a list of code points (a lone surrogate
/// is one, as in a Python `str`).
#[derive(Debug)]
pub enum Json {
    Null,
    Bool(bool),
    /// Decimal digits, a `-` only for a non-zero negative number.
    Int(String),
    Float(f64),
    Str(Vec<u32>),
    Array(Vec<Json>),
    /// Keys are unique; insertion order.
    Object(Vec<(Vec<u32>, Json)>),
}

impl Json {
    /// A value `serde_json` already parsed (an integer beyond 64 bits is
    /// already a float there).
    pub fn from_value(value: &Value) -> Json {
        match value {
            Value::Null => Json::Null,
            Value::Bool(b) => Json::Bool(*b),
            Value::Number(n) => {
                if let Some(i) = n.as_i64() {
                    Json::Int(i.to_string())
                } else if let Some(u) = n.as_u64() {
                    Json::Int(u.to_string())
                } else {
                    Json::Float(n.as_f64().unwrap_or(f64::NAN))
                }
            }
            Value::String(s) => Json::Str(s.chars().map(u32::from).collect()),
            Value::Array(items) => Json::Array(items.iter().map(Json::from_value).collect()),
            Value::Object(map) => Json::Object(
                map.iter()
                    .map(|(k, v)| (k.chars().map(u32::from).collect(), Json::from_value(v)))
                    .collect(),
            ),
        }
    }

    pub fn str(text: &str) -> Json {
        Json::Str(text.chars().map(u32::from).collect())
    }

    /// `value.get(key)` of an object.
    pub fn get(&self, key: &str) -> Option<&Json> {
        let Json::Object(entries) = self else {
            return None;
        };
        let wanted: Vec<u32> = key.chars().map(u32::from).collect();
        entries.iter().find(|(k, _)| *k == wanted).map(|(_, v)| v)
    }

    pub fn dumps(&self, options: Options) -> String {
        let mut out = String::new();
        self.write(options, &mut out);
        out
    }

    /// `json.dumps(value, sort_keys=True, separators=(",", ":"))`.
    pub fn canonical(&self) -> String {
        self.dumps(CANONICAL)
    }

    /// Writes the value with an explicit work list, not recursion.
    fn write(&self, options: Options, out: &mut String) {
        enum Task<'a> {
            Value(&'a Json),
            Text(&'static str),
            Key(&'a [u32]),
        }
        let (item, key) = if options.compact {
            (",", ":")
        } else {
            (", ", ": ")
        };
        let mut work = vec![Task::Value(self)];
        while let Some(task) = work.pop() {
            let value = match task {
                Task::Text(text) => {
                    out.push_str(text);
                    continue;
                }
                Task::Key(points) => {
                    code_points(points, out);
                    continue;
                }
                Task::Value(value) => value,
            };
            match value {
                Json::Null => out.push_str("null"),
                Json::Bool(true) => out.push_str("true"),
                Json::Bool(false) => out.push_str("false"),
                Json::Int(digits) => out.push_str(digits),
                Json::Float(f) => out.push_str(&float_repr(*f)),
                Json::Str(chars) => code_points(chars, out),
                Json::Array(items) => {
                    out.push('[');
                    work.push(Task::Text("]"));
                    for (i, v) in items.iter().enumerate().rev() {
                        work.push(Task::Value(v));
                        if i > 0 {
                            work.push(Task::Text(item));
                        }
                    }
                }
                Json::Object(entries) => {
                    out.push('{');
                    work.push(Task::Text("}"));
                    let mut order: Vec<&(Vec<u32>, Json)> = entries.iter().collect();
                    if options.sort_keys {
                        // code point order, as Python sorts `str`
                        order.sort_by(|a, b| a.0.cmp(&b.0));
                    }
                    for (i, (k, v)) in order.into_iter().enumerate().rev() {
                        work.push(Task::Value(v));
                        work.push(Task::Text(key));
                        work.push(Task::Key(k));
                        if i > 0 {
                            work.push(Task::Text(item));
                        }
                    }
                }
            }
        }
    }
}

/// A value nested to the depth limit is dropped without recursing.
impl Drop for Json {
    fn drop(&mut self) {
        fn children(value: &mut Json, into: &mut Vec<Json>) {
            match value {
                Json::Array(items) => into.append(items),
                Json::Object(entries) => into.extend(entries.drain(..).map(|(_, v)| v)),
                _ => {}
            }
        }
        let mut pending = Vec::new();
        children(self, &mut pending);
        while let Some(mut value) = pending.pop() {
            children(&mut value, &mut pending);
        }
    }
}

/// `json.dumps(value, ...)` of a `serde_json::Value`.
pub fn dumps(value: &Value, options: Options) -> String {
    Json::from_value(value).dumps(options)
}

/// A JSON string with everything outside space..`~` escaped (`ensure_ascii`).
pub fn string(s: &str, out: &mut String) {
    let points: Vec<u32> = s.chars().map(u32::from).collect();
    code_points(&points, out);
}

fn code_points(points: &[u32], out: &mut String) {
    out.push('"');
    for &cp in points {
        match cp {
            0x22 => out.push_str("\\\""),
            0x5c => out.push_str("\\\\"),
            0x0a => out.push_str("\\n"),
            0x0d => out.push_str("\\r"),
            0x09 => out.push_str("\\t"),
            0x08 => out.push_str("\\b"),
            0x0c => out.push_str("\\f"),
            0x20..=0x7e => out.push(char::from(u8::try_from(cp).unwrap_or(b'?'))),
            0x10000.. => {
                let v = cp - 0x10000;
                let _ = write!(
                    out,
                    "\\u{:04x}\\u{:04x}",
                    0xd800 + (v >> 10),
                    0xdc00 + (v & 0x3ff)
                );
            }
            _ => {
                let _ = write!(out, "\\u{cp:04x}");
            }
        }
    }
    out.push('"');
}

/// `json.dumps("text")` for one string.
pub fn quote(s: &str) -> String {
    let mut out = String::new();
    string(s, &mut out);
    out
}

/// `repr(float)`, which is also what `json.dumps` writes for a float.
pub fn float_repr(f: f64) -> String {
    if f.is_nan() {
        return "NaN".into();
    }
    if f.is_infinite() {
        return if f < 0.0 { "-Infinity" } else { "Infinity" }.into();
    }
    let sign = if f.is_sign_negative() { "-" } else { "" };
    if f == 0.0 {
        return format!("{sign}0.0");
    }
    let sci = format!("{:e}", f.abs());
    let (mantissa, exp) = sci.split_once('e').unwrap_or((&sci, "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    if (-4..16).contains(&exp) {
        if exp >= 0 {
            let int_len = usize::try_from(exp).unwrap_or(0) + 1;
            let mut int_part = digits.clone();
            while int_part.len() < int_len {
                int_part.push('0');
            }
            let (whole, frac) = int_part.split_at(int_len);
            let frac = if frac.is_empty() { "0" } else { frac };
            format!("{sign}{whole}.{frac}")
        } else {
            format!(
                "{sign}0.{}{digits}",
                "0".repeat(usize::try_from(-exp - 1).unwrap_or(0))
            )
        }
    } else {
        let head = &digits[..1];
        let tail = &digits[1..];
        let point = if tail.is_empty() {
            String::new()
        } else {
            format!(".{tail}")
        };
        let esign = if exp < 0 { '-' } else { '+' };
        format!("{sign}{head}{point}e{esign}{:02}", exp.abs())
    }
}

// ---------------------------------------------------------------- parse ----

/// `json.loads(body)` of a request body; `None` where Python raises
/// `ValueError` and where this reader declines (see the module notes).
pub fn parse(body: &[u8]) -> Option<Json> {
    parse_limited(body, MAX_DEPTH)
}

/// [`parse`] with another nesting limit.
pub fn parse_limited(body: &[u8], max_depth: usize) -> Option<Json> {
    // `json.detect_encoding`: UTF-16 and UTF-32 bodies are not read here
    match body {
        [0xff, 0xfe, ..] | [0xfe, 0xff, ..] | [0, ..] | [_, 0, ..] => return None,
        _ => {}
    }
    let body = body.strip_prefix(&[0xef, 0xbb, 0xbf]).unwrap_or(body);
    let text = std::str::from_utf8(body).ok()?;
    let mut parser = Parser {
        src: text,
        text: text.as_bytes(),
        at: 0,
        max_depth,
    };
    parser.skip_ws();
    let value = parser.value()?;
    parser.skip_ws();
    (parser.at == parser.text.len()).then_some(value)
}

/// A container being read.
enum Frame {
    Array(Vec<Json>),
    /// The members so far and the name whose value is being read.
    Object(ObjectBuilder, Option<Vec<u32>>),
}

/// The members of an object under construction: a repeated name keeps its
/// first place and takes its last value. A small object is searched; a large
/// one is indexed by a hash map with the standard library's keyed hasher
/// (`RandomState`), so reading is linear in the body and a crafted set of keys
/// cannot force collisions.
struct ObjectBuilder {
    entries: Vec<(Vec<u32>, Json)>,
    index: Option<std::collections::HashMap<Vec<u32>, usize>>,
}

/// Members searched one by one before an index is built.
const SCAN_LIMIT: usize = 8;

impl ObjectBuilder {
    fn new() -> ObjectBuilder {
        ObjectBuilder {
            entries: Vec::new(),
            index: None,
        }
    }

    fn insert(&mut self, key: Vec<u32>, value: Json) {
        let position = match &self.index {
            Some(index) => index.get(&key).copied(),
            None => self.entries.iter().position(|(k, _)| *k == key),
        };
        if let Some(position) = position {
            self.entries[position].1 = value;
            return;
        }
        if let Some(index) = &mut self.index {
            index.insert(key.clone(), self.entries.len());
        } else if self.entries.len() >= SCAN_LIMIT {
            let mut index: std::collections::HashMap<Vec<u32>, usize> = self
                .entries
                .iter()
                .enumerate()
                .map(|(i, (k, _))| (k.clone(), i))
                .collect();
            index.insert(key.clone(), self.entries.len());
            self.index = Some(index);
        }
        self.entries.push((key, value));
    }

    fn into_entries(self) -> Vec<(Vec<u32>, Json)> {
        self.entries
    }
}

struct Parser<'a> {
    src: &'a str,
    text: &'a [u8],
    at: usize,
    max_depth: usize,
}

impl Parser<'_> {
    fn skip_ws(&mut self) {
        while matches!(self.text.get(self.at), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.at += 1;
        }
    }

    fn peek(&self) -> Option<u8> {
        self.text.get(self.at).copied()
    }

    fn eat(&mut self, literal: &[u8]) -> bool {
        if self.text[self.at..].starts_with(literal) {
            self.at += literal.len();
            true
        } else {
            false
        }
    }

    /// One scalar, or `None`. A container start is not handled here.
    fn scalar(&mut self) -> Option<Json> {
        match self.peek()? {
            b'"' => self.string().map(Json::Str),
            b'n' => self.eat(b"null").then_some(Json::Null),
            b't' => self.eat(b"true").then_some(Json::Bool(true)),
            b'f' => self.eat(b"false").then_some(Json::Bool(false)),
            b'N' => self.eat(b"NaN").then_some(Json::Float(f64::NAN)),
            b'I' => self.eat(b"Infinity").then_some(Json::Float(f64::INFINITY)),
            b'-' if self.text[self.at..].starts_with(b"-Infinity") => {
                self.at += b"-Infinity".len();
                Some(Json::Float(f64::NEG_INFINITY))
            }
            b'-' | b'0'..=b'9' => self.number(),
            _ => None,
        }
    }

    /// A value, with an explicit stack of the containers being read.
    fn value(&mut self) -> Option<Json> {
        let mut stack: Vec<Frame> = Vec::new();
        loop {
            self.skip_ws();
            let mut done = match self.peek()? {
                b'[' => {
                    self.at += 1;
                    if stack.len() >= self.max_depth {
                        return None;
                    }
                    self.skip_ws();
                    if self.peek() == Some(b']') {
                        self.at += 1;
                        Json::Array(Vec::new())
                    } else {
                        stack.push(Frame::Array(Vec::new()));
                        continue;
                    }
                }
                b'{' => {
                    self.at += 1;
                    if stack.len() >= self.max_depth {
                        return None;
                    }
                    self.skip_ws();
                    if self.peek() == Some(b'}') {
                        self.at += 1;
                        Json::Object(Vec::new())
                    } else {
                        let key = self.member_key()?;
                        stack.push(Frame::Object(ObjectBuilder::new(), Some(key)));
                        continue;
                    }
                }
                _ => self.scalar()?,
            };
            // attach the finished value to its parent, closing what it ends
            loop {
                match stack.last_mut() {
                    None => return Some(done),
                    Some(Frame::Array(items)) => {
                        items.push(done);
                        self.skip_ws();
                        match self.peek()? {
                            b',' => {
                                self.at += 1;
                                break;
                            }
                            b']' => {
                                self.at += 1;
                                let Some(Frame::Array(items)) = stack.pop() else {
                                    return None;
                                };
                                done = Json::Array(items);
                            }
                            _ => return None,
                        }
                    }
                    Some(Frame::Object(members, key)) => {
                        members.insert(key.take()?, done);
                        self.skip_ws();
                        match self.peek()? {
                            b',' => {
                                self.at += 1;
                                self.skip_ws();
                                *key = Some(self.member_key()?);
                                break;
                            }
                            b'}' => {
                                self.at += 1;
                                let Some(Frame::Object(members, _)) = stack.pop() else {
                                    return None;
                                };
                                done = Json::Object(members.into_entries());
                            }
                            _ => return None,
                        }
                    }
                }
            }
        }
    }

    /// A member name and its colon.
    fn member_key(&mut self) -> Option<Vec<u32>> {
        self.skip_ws();
        if self.peek()? != b'"' {
            return None;
        }
        let key = self.string()?;
        self.skip_ws();
        if self.peek()? != b':' {
            return None;
        }
        self.at += 1;
        Some(key)
    }

    fn number(&mut self) -> Option<Json> {
        let start = self.at;
        if self.peek() == Some(b'-') {
            self.at += 1;
        }
        match self.peek()? {
            b'0' => self.at += 1,
            b'1'..=b'9' => self.digits(),
            _ => return None,
        }
        let mut float = false;
        // a fraction needs a digit after the point, else the point is left
        // over (and the caller sees trailing data)
        if self.peek() == Some(b'.') && self.text.get(self.at + 1).is_some_and(u8::is_ascii_digit) {
            self.at += 1;
            self.digits();
            float = true;
        }
        if matches!(self.peek(), Some(b'e' | b'E')) {
            let mut look = self.at + 1;
            if matches!(self.text.get(look), Some(b'+' | b'-')) {
                look += 1;
            }
            if self.text.get(look).is_some_and(u8::is_ascii_digit) {
                self.at = look;
                self.digits();
                float = true;
            }
        }
        let token = std::str::from_utf8(&self.text[start..self.at]).ok()?;
        if float {
            return token.parse::<f64>().ok().map(Json::Float);
        }
        let (negative, digits) = token
            .strip_prefix('-')
            .map_or((false, token), |d| (true, d));
        if digits.len() > MAX_INT_DIGITS {
            return None;
        }
        let zero = digits == "0";
        Some(Json::Int(if negative && !zero {
            format!("-{digits}")
        } else {
            digits.to_string()
        }))
    }

    fn digits(&mut self) {
        while self.peek().is_some_and(|b| b.is_ascii_digit()) {
            self.at += 1;
        }
    }

    fn hex4(&mut self) -> Option<u32> {
        let slice = self.text.get(self.at..self.at + 4)?;
        let mut value = 0u32;
        for &b in slice {
            value = value * 16 + char::from(b).to_digit(16)?;
        }
        self.at += 4;
        Some(value)
    }

    fn string(&mut self) -> Option<Vec<u32>> {
        self.at += 1; // the opening quote
        let mut out: Vec<u32> = Vec::new();
        loop {
            let byte = self.peek()?;
            match byte {
                b'"' => {
                    self.at += 1;
                    return Some(out);
                }
                b'\\' => {
                    self.at += 1;
                    let escape = self.peek()?;
                    self.at += 1;
                    let cp = match escape {
                        b'"' => 0x22,
                        b'\\' => 0x5c,
                        b'/' => 0x2f,
                        b'b' => 0x08,
                        b'f' => 0x0c,
                        b'n' => 0x0a,
                        b'r' => 0x0d,
                        b't' => 0x09,
                        b'u' => {
                            let first = self.hex4()?;
                            if (0xd800..=0xdbff).contains(&first)
                                && self.text[self.at..].starts_with(b"\\u")
                            {
                                let saved = self.at;
                                self.at += 2;
                                match self.hex4() {
                                    Some(second) if (0xdc00..=0xdfff).contains(&second) => {
                                        0x10000 + ((first - 0xd800) << 10) + (second - 0xdc00)
                                    }
                                    _ => {
                                        // not a pair: the first stands alone
                                        self.at = saved;
                                        first
                                    }
                                }
                            } else {
                                first
                            }
                        }
                        _ => return None,
                    };
                    out.push(cp);
                }
                0..=0x1f => return None, // a control character (strict mode)
                _ => {
                    // the text is valid UTF-8: take one whole character
                    let c = self.src.get(self.at..)?.chars().next()?;
                    self.at += c.len_utf8();
                    out.push(u32::from(c));
                }
            }
        }
    }
}
