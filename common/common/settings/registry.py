"""The settings registry: what a setting is, who may read it, how it is
validated and how a change to it takes effect.

A setting's store key is its environment variable name. Adding a key is one
declarative ``SettingSpec`` in ``SEED_SPECS``; the registry refuses specs that
contradict each other (see ``SettingSpec.__post_init__``) and validates values
by type and policy. Error messages name the key and the rule, never the value.

URL and host checks are text checks on what an administrator types. They do
not see DNS: any client that connects to a configured URL (AI endpoint,
webhook, SSO bridge, mail server) must re-check the resolved IP address at
connect time (``not ip.is_global``, with the same ``internal_ok`` exception)
and must not follow redirects blindly.
"""

from __future__ import annotations

import ipaddress
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Iterable, Iterator, Mapping, Optional, Tuple
from urllib.parse import urlsplit

from .secret_checks import SECRET_FORMATS, FormatCheck

__all__ = [
    "ENV_ONLY_KEYS",
    "SEED_SPECS",
    "Registry",
    "RegistryError",
    "Reload",
    "SettingSpec",
    "Tier",
    "UnknownKeyError",
    "ValidationError",
    "ValueType",
    "default_registry",
    "normalize_value",
]

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
MAX_STRING = 8192
MAX_SECRET = 4096
MAX_JSON_BYTES = 65536
MAX_URL = 2048


class Reload(str, Enum):
    """How a change takes effect in a reading service."""

    B = "B"  # build time: needs a new image
    H = "H"  # hot: read live, no restart
    R = "R"  # restart: picked up when the service restarts


class Tier(str, Enum):
    T1 = "T1"  # audit only
    T2 = "T2"  # step-up, audit, notify admins
    T3 = "T3"  # T2 + typed confirmation + URL/SSRF check
    T4 = "T4"  # managed by a task only (key material)
    T5 = "T5"  # environment only, never in the store


class ValueType(str, Enum):
    STR = "str"
    INT = "int"
    BOOL = "bool"
    FLOAT = "float"
    URL = "url"
    JSON = "json"
    ENUM = "enum"


# Keys that may only ever come from the environment (tier T5). The prefixes
# below cover the ADMIN_*, JOBS_* and DB_* families.
ENV_ONLY_KEYS = frozenset(
    {
        "DATABASE_URL",
        "TASKS_DATABASE_URL",
        "SETTINGS_MASTER_KEY",
        "SETTINGS_MASTER_KEY_PREVIOUS",
        "SETTINGS_STORE",
        "PLATFORM_ADMIN_EMAILS",
        "DB_READ_SOURCE",
        "DB_WRITE_MODE",
        "PDF_IMPORT_REQUIRE_ISOLATED_SANDBOX",
        "PDF_IMPORT_SANDBOX_SOCKET",
        "DOC_SANDBOX_PARALLEL",
        "DOC_SANDBOX_MAX_DOCUMENT_BYTES",
        "DOTENV_PATH",
        "PROJECT_NAME",
        "DOCS_URL",
        "VERSION",
        "PORT",
        "TEMPLATE_FOLDER",
        "AUTH_BASE_URL",
        "AUTH_SERVER_URL",
        "TEMPORAL_SERVER_URI",
        "TEMPORAL_NAMESPACE",
        "TEMPORAL_TEMPLATE_PREVIEW_QUEUE",
        "TEMPORAL_WORKER_QUEUE",
        "TEMPORAL_ACTION_QUEUE",
        "TEMPORAL_CSV_QUEUE",
        "TEMPORAL_SERVER_URL",
        "NAMESPACE",
        "SERVER_URL",
        "BACKEND_URL",
        "FRONTEND_URL",
        "API_KEY",
        "AES_HEX_KEY",
        "WORKER_QUEUE",
        "WORKERS",
        "COOKIE_DOMAIN",
        "MAX_THREAD_POOL_EXECUTORS",
        "ELASTIC_APM_SERVICE_NAME",
        "ELASTIC_APM_SERVER_URL",
        "ELASTIC_APM_API_KEY",
        "ELASTIC_APM_SECRET_TOKEN",
        "ELASTIC_APM_ENVIRONMENT",
        "ELASTIC_APM_ENABLED",
        "NEXT_PUBLIC_API_ENDPOINT_HOST",
        "NEXT_PUBLIC_NODE_ENV",
        "NEXT_PUBLIC_DASHBOARD_DOMAIN",
        "NEXT_PUBLIC_APP_URL",
        "BASE_DEPLOY_PATH",
        "API_ENDPOINT_HOST",
        "INTERNAL_DOCKER_API_ENDPOINT_HOST",
        "HTTP_SCHEME",
        "FORM_DOMAIN",
        "DASHBOARD_DOMAIN",
        "FORM_PRIVACY_POLICY_URL",
        "GOOGLE_PICKER_API_KEY",
        "UMAMI_SCRIPT_URL",
        "CUSTOM_DOMAIN_ASSERTION_MODE",
        "CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN",
    }
)
ENV_ONLY_PREFIXES = ("ADMIN_", "JOBS_", "DB_")


class RegistryError(ValueError):
    """A spec or the registry itself is inconsistent."""


class ValidationError(ValueError):
    """A value was refused. ``reason`` is a short code; the message names the
    key and the rule, never the value."""

    def __init__(self, key: str, reason: str, message: str = ""):
        self.key = key
        self.reason = reason
        super().__init__(f"{key}: {message or reason}")


class UnknownKeyError(ValidationError):
    def __init__(self, key: str):
        super().__init__(key, "unknown_key", "not a known setting")


# The admin sign-in mail settings (section ``admin_mail``) are the one family of
# ``ADMIN_`` names that may live in the store; the environment still wins.
STORE_PREFIXES = ("ADMIN_MAIL_",)


def is_env_only(key: str) -> bool:
    if key.startswith(STORE_PREFIXES):
        return key in ENV_ONLY_KEYS
    return key in ENV_ONLY_KEYS or key.startswith(ENV_ONLY_PREFIXES)


def normalize_value(value: Optional[str]) -> str:
    """The value as an env file means it: trimmed, one pair of quotes removed.
    Same rule as ``common.configs.shipped_secrets.normalize_secret`` (kept
    here so this package imports nothing outside itself; a test pins them)."""
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1].strip()
    return value


@dataclass(frozen=True)
class SettingSpec:
    key: str
    section: str
    readers: Tuple[str, ...]
    type: ValueType = ValueType.STR
    is_secret: bool = False
    reload_class: Reload = Reload.R
    tier: Tier = Tier.T1
    default: Any = None
    internal_ok: bool = False  # http and compose-network hosts allowed (URL only)
    description: str = ""
    choices: Tuple[str, ...] = ()
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_length: Optional[int] = None
    # for strings: "cidr_list", "ip_list" or "host"; for secrets one of
    # ``secret_checks.SECRET_FORMATS``
    format: str = ""
    # services that were once readers: rows written then still list them, and a
    # reader accepts such a row (its signature covers the old list) instead of
    # refusing it as a changed spec; the next write drops the name
    retired_readers: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        def bad(msg: str) -> None:
            raise RegistryError(f"{self.key or '?'}: {msg}")

        if not KEY_RE.match(self.key or ""):
            bad("key must be an upper-case env var name")
        if not NAME_RE.match(self.section or ""):
            bad("section must be a short lower-case name")
        if not self.readers or any(not NAME_RE.match(r or "") for r in self.readers):
            bad("readers must be a non-empty tuple of service names")
        if len(set(self.readers)) != len(self.readers):
            bad("duplicate readers")
        if any(not NAME_RE.match(r or "") for r in self.retired_readers) or set(
            self.retired_readers
        ) & set(self.readers):
            bad("retired readers must be names that are not current readers")
        if not isinstance(self.type, ValueType):
            bad("unknown type")
        if not isinstance(self.reload_class, Reload):
            bad("unknown reload class")
        if not isinstance(self.tier, Tier):
            bad("unknown tier")
        if self.tier is Tier.T4 and self.reload_class is Reload.H:
            bad("a T4 key is never hot-reloaded")
        if self.is_secret:
            if self.reload_class is Reload.H:
                bad("a secret is never hot-reloaded")
            if self.type is not ValueType.STR:
                bad("a secret must be a string")
            if self.tier is Tier.T1:
                bad("a secret needs tier T2 or higher")
            if self.default is not None:
                bad("a secret has no default")
        if self.tier is Tier.T4 and not self.is_secret:
            bad("T4 is for key material, which is secret")
        if self.type is ValueType.ENUM and not self.choices:
            bad("an enum needs choices")
        if self.type is not ValueType.ENUM and self.choices:
            bad("choices apply to enums only")
        if self.internal_ok and self.type is not ValueType.URL:
            bad("internal_ok applies to URLs only")
        if self.type is ValueType.URL and self.tier not in (Tier.T3, Tier.T4, Tier.T5):
            bad("a URL setting needs tier T3 (typed confirmation and SSRF check)")
        numeric = self.type in (ValueType.INT, ValueType.FLOAT)
        if (self.min_value is not None or self.max_value is not None) and not numeric:
            bad("ranges apply to numbers only")
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            bad("empty range")
        if self.max_length is not None and self.type is not ValueType.STR:
            bad("max_length applies to strings only")
        plain_formats = ("cidr_list", "ip_list", "host")
        if self.format and self.format not in plain_formats + tuple(SECRET_FORMATS):
            bad("unknown format")
        if self.format and self.type is not ValueType.STR:
            bad("a format applies to strings only")
        if self.format in plain_formats and self.is_secret:
            bad("this format applies to plain strings only")
        if self.format in SECRET_FORMATS and not self.is_secret:
            bad("this format applies to secrets only")
        if self.default is not None:
            try:
                coerce_value(self, self.default)
                if self.type is ValueType.URL:
                    check_policy_url(self, self.default)
            except ValidationError as exc:
                bad(f"default is invalid ({exc.reason})")

    @property
    def storable(self) -> bool:
        return self.tier is not Tier.T5


# ------------------------------------------------------------ typed parsing

_INT = re.compile(r"[+-]?[0-9]+", re.ASCII)
_FLOAT = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?", re.ASCII)
_TRUE = frozenset({"true", "1", "yes", "on"})
_FALSE = frozenset({"false", "0", "no", "off"})


def _fail(spec: SettingSpec, reason: str, message: str = "") -> ValidationError:
    return ValidationError(spec.key, reason, message)


_BIDI = frozenset(
    list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A)) + [0x200E, 0x200F, 0x061C]
)


def _is_control(char: str) -> bool:
    """C0/C1 controls, DEL, line and paragraph separators, bidi controls."""
    return (
        unicodedata.category(char) in ("Cc", "Zl", "Zp") or ord(char) in _BIDI
    )


def coerce_value(spec: SettingSpec, raw: Any) -> Any:
    """``raw`` (env text or an already typed store value) as the spec's type.
    Type rules only; policy (URL safety, secret strength) is ``Registry.validate``."""
    t = spec.type
    if t is ValueType.BOOL:
        if isinstance(raw, bool):
            return raw
        text = raw.strip().lower() if isinstance(raw, str) else None
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise _fail(spec, "not_bool", "expected true or false")
    if t in (ValueType.INT, ValueType.FLOAT):
        if isinstance(raw, bool):
            raise _fail(spec, "not_number", f"expected a {t.value}")
        try:
            text = raw.strip() if isinstance(raw, str) else None
            if t is ValueType.INT:
                if isinstance(raw, float) and not raw.is_integer():
                    raise ValueError
                if text is not None and not _INT.fullmatch(text):
                    raise ValueError  # "1_000", non-ASCII digits, "0x10"
                number: Any = int(text if text is not None else raw)
            else:
                if text is not None and not _FLOAT.fullmatch(text):
                    raise ValueError
                number = float(text if text is not None else raw)
                if not math.isfinite(number):
                    raise ValueError
        except (TypeError, ValueError, OverflowError):
            raise _fail(spec, "not_number", f"expected a {t.value}") from None
        if spec.min_value is not None and number < spec.min_value:
            raise _fail(spec, "out_of_range", f"must be at least {spec.min_value:g}")
        if spec.max_value is not None and number > spec.max_value:
            raise _fail(spec, "out_of_range", f"must be at most {spec.max_value:g}")
        return number
    if t is ValueType.JSON:
        try:
            parsed = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            encoded = json.dumps(parsed, allow_nan=False)
        except (TypeError, ValueError):
            raise _fail(spec, "not_json", "expected JSON") from None
        if not isinstance(parsed, (dict, list)):
            raise _fail(spec, "not_json", "expected a JSON object or array")
        if len(encoded) > MAX_JSON_BYTES:
            raise _fail(spec, "too_long")
        return parsed
    if not isinstance(raw, str):
        raise _fail(spec, "not_string", "expected text")
    if t is ValueType.ENUM:
        if raw not in spec.choices:
            raise _fail(
                spec, "not_a_choice", f"expected one of {', '.join(spec.choices)}"
            )
        return raw
    limit = MAX_SECRET if spec.is_secret else (spec.max_length or MAX_STRING)
    if t is ValueType.URL:
        limit = MAX_URL
    if len(raw) > limit:
        raise _fail(spec, "too_long")
    if any(_is_control(c) for c in raw):
        raise _fail(spec, "control_characters")
    if spec.format == "cidr_list":
        parse_cidr_list(spec, raw)
    elif spec.format == "ip_list":
        problem = ip_list_problem(raw)
        if problem:
            raise _fail(spec, "bad_ip_list", problem)
    elif spec.format == "host":
        check_host_syntax(spec, raw)
    return raw


# ------------------------------------------------------------ URL policy

BLOCKED_NAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata",
        "metadata.google.internal",
        "instance-data",
        "instance-data.ec2.internal",
        "kubernetes.default.svc",
    }
)
METADATA_ADDRESSES = frozenset(
    ipaddress.ip_address(a)
    for a in ("169.254.169.254", "100.100.100.200", "192.0.0.192", "fd00:ec2::254")
)
_NUMERIC_LABEL = re.compile(r"^(0[xX][0-9a-fA-F]*|[0-9]+)$")
# Names that resolve to whatever address they spell (wildcard DNS).
WILDCARD_DNS_SUFFIXES = (
    "nip.io",
    "sslip.io",
    "xip.io",
    "traefik.me",
    "localtest.me",
    "lvh.me",
    "vcap.me",
    "lacolhost.com",
)
_EMBEDDED_V4 = re.compile(r"(?<![0-9])([0-9]{1,3})[.-]([0-9]{1,3})[.-]([0-9]{1,3})[.-]([0-9]{1,3})(?![0-9])")
# The only non-public ranges ``internal_ok`` admits: private networks.
INTERNAL_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)


def _address_problem(address, internal_ok: bool) -> Optional[str]:
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    if address in METADATA_ADDRESSES:
        return "refers to a cloud metadata service"
    if address.is_loopback or address.is_unspecified or address.is_link_local:
        return "refers to this machine or a link-local address"
    if address.is_multicast:
        return "is a multicast address"
    if address.is_global:
        return None
    if internal_ok and any(address in net for net in INTERNAL_NETWORKS):
        return None
    return "is not a public address"


def _host_problem(host: str, internal_ok: bool) -> Optional[str]:
    host = host.rstrip(".").lower()
    if not host:
        return "is missing"
    if host in BLOCKED_NAMES or host.endswith(".localhost"):
        return "refers to this machine or a metadata service"
    numeric_like = all(_NUMERIC_LABEL.match(label) for label in host.split("."))
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if numeric_like:  # 2130706433, 0x7f000001, 0177.0.0.1, 127.1
            return "uses an ambiguous IP address spelling"
        if any(host == s or host.endswith("." + s) for s in WILDCARD_DNS_SUFFIXES):
            return "uses a wildcard DNS name that can point anywhere"
        for found in _EMBEDDED_V4.finditer(host):
            try:
                embedded = ipaddress.IPv4Address(".".join(found.groups()))
            except ValueError:
                continue
            if _address_problem(embedded, internal_ok):
                return "embeds a non-public IP address"
        return None
    return _address_problem(address, internal_ok)


def check_host_syntax(spec: SettingSpec, value: str) -> None:
    """A bare host name or IP address: no scheme, userinfo, port, path or spaces."""
    text = value
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    try:
        ipaddress.ip_address(text)
        return
    except ValueError:
        pass
    labels = text.rstrip(".").split(".")
    ok = (
        0 < len(text) <= 253
        and all(re.fullmatch(r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?", l, re.ASCII) for l in labels)
    )
    if not ok:
        raise _fail(spec, "bad_host", "must be a host name or IP address only")


MAX_PROXIES = 64
MIN_PREFIX = {4: 8, 6: 32}  # narrower than this is "everyone"


def parse_cidr_list(spec: SettingSpec, value: str):
    """Comma separated addresses and CIDRs; syntax only."""
    if not value.strip():
        return []
    items = [part.strip() for part in value.split(",")]
    if len(items) > MAX_PROXIES or any(not item for item in items):
        raise _fail(spec, "bad_cidr_list", "expected comma separated addresses or CIDRs")
    networks = []
    for item in items:
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            raise _fail(spec, "bad_cidr_list", "contains an invalid address or CIDR") from None
    return networks


MAX_IP_LIST = 16


def parse_ip_list(value: str) -> list:
    """Comma separated IPv4/IPv6 addresses, whitespace around each tolerated;
    empty is an empty list. ValueError (with ``ip_list_problem``'s text) for
    anything else: a host name, a CIDR, a port, a URL, another separator."""
    if not value.strip():
        return []
    items = [part.strip() for part in value.split(",")]
    if len(items) > MAX_IP_LIST:
        raise ValueError(f"at most {MAX_IP_LIST} addresses")
    addresses = []
    for item in items:
        try:
            if not item or "%" in item:
                raise ValueError
            addresses.append(ipaddress.ip_address(item))
        except ValueError:
            raise ValueError(
                "expected comma separated IP addresses (IPv4 or IPv6), "
                "not host names, ports or other separators"
            ) from None
    return addresses


def ip_list_problem(value: str) -> Optional[str]:
    """Why ``value`` is not a comma separated list of IP addresses, or None."""
    try:
        parse_ip_list(value)
    except ValueError as exc:
        return str(exc)
    return None


def check_policy_cidrs(spec: SettingSpec, value: str) -> None:
    """Refuse a list that would trust (nearly) everyone: any /0, IPv4 wider
    than /8 and IPv6 wider than /32."""
    for net in parse_cidr_list(spec, value):
        if net.prefixlen < MIN_PREFIX[net.version]:
            raise _fail(spec, "too_wide", "trusts too wide a range of addresses")


def check_policy_url(spec: SettingSpec, value: str) -> None:
    """https only (http too when ``internal_ok``), no userinfo, and no host
    that points at this machine, link-local space or a metadata service."""
    if value != value.strip() or any(c.isspace() for c in value):
        raise _fail(spec, "bad_url", "must not contain whitespace")
    try:
        parts = urlsplit(value)
        parts.port  # noqa: B018 - raises ValueError for a bad port
    except ValueError:
        raise _fail(spec, "bad_url", "not a valid URL") from None
    allowed = ("https", "http") if spec.internal_ok else ("https",)
    if parts.scheme.lower() not in allowed:
        raise _fail(
            spec,
            "bad_scheme",
            "must use http or https" if spec.internal_ok else "must use https",
        )
    if "@" in parts.netloc:
        raise _fail(spec, "userinfo", "must not contain credentials")
    problem = _host_problem(parts.hostname or "", spec.internal_ok)
    if problem:
        raise _fail(spec, "blocked_host", f"host {problem}")


SecretCheck = Callable[[str, str], Iterable[str]]


# ------------------------------------------------------------ the registry


class Registry:
    def __init__(
        self,
        specs: Iterable[SettingSpec] = (),
        *,
        secret_problems: Optional[SecretCheck] = None,
        format_checks: Optional[Mapping[str, FormatCheck]] = None,
        retired: Iterable[str] = (),
    ):
        """``retired`` names keys that were settings once and no longer are: a
        stored row of one is ignored (neither applied nor reported as refused).

        ``secret_problems(key, value)`` returns one line per problem with
        the secret (lines name the key, never the value). For example
        ``lambda k, v: shipped_secrets.secret_problems(jwt_secrets={k: v})``.

        ``format_checks`` maps a secret's ``format`` to its check (see
        ``secret_checks``). A registry built with it (the store's writers) refuses
        a malformed or weak secret with the check's code; one built without it
        (the readers) accepts whatever the writers stored."""
        self._specs: Dict[str, SettingSpec] = {}
        self._secret_problems = secret_problems
        self._format_checks = None if format_checks is None else dict(format_checks)
        self.retired: frozenset = frozenset(retired)
        for spec in specs:
            self.register(spec)

    def register(self, spec: SettingSpec) -> SettingSpec:
        if not spec.storable or is_env_only(spec.key):
            raise RegistryError(f"{spec.key}: environment-only keys are not store keys")
        if spec.key in self._specs:
            raise RegistryError(f"{spec.key}: registered twice")
        if spec.key in self.retired:
            raise RegistryError(f"{spec.key}: retired keys are not registered")
        self._specs[spec.key] = spec
        return spec

    def __contains__(self, key: object) -> bool:
        return key in self._specs

    def __iter__(self) -> Iterator[SettingSpec]:
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)

    def get(self, key: str) -> SettingSpec:
        spec = self._specs.get(key) if isinstance(key, str) else None
        if spec is None:
            raise UnknownKeyError(str(key)[:64])
        return spec

    def keys(self) -> Tuple[str, ...]:
        return tuple(sorted(self._specs))

    def for_reader(self, service: str) -> Tuple[SettingSpec, ...]:
        return tuple(s for s in self if service in s.readers)

    def coerce(self, key: str, raw: Any) -> Any:
        """Type check only (for values that come from the environment)."""
        return coerce_value(self.get(key), raw)

    def validate(self, key: str, raw: Any) -> Any:
        """The typed value for ``raw``, or ValidationError. Rejects unknown
        keys, enforces ranges and enums, URL safety and secret strength."""
        spec = self.get(key)
        value = coerce_value(spec, raw)
        if spec.is_secret:
            if not value or normalize_value(value) != value:
                raise _fail(
                    spec,
                    "bad_secret",
                    "must be non-empty, without surrounding whitespace or quotes",
                )
            if self._secret_problems is None:
                raise _fail(spec, "no_secret_check", "no secret check configured")
            problems = list(self._secret_problems(spec.key, value))
            if problems:
                raise _fail(spec, "weak_secret", "; ".join(problems))
            if self._format_checks is not None and spec.format:
                check = self._format_checks.get(spec.format)
                if check is None:  # fail closed: a format nobody can check
                    raise _fail(spec, "no_secret_check", "no check for this key's format")
                found = check(value)
                if found:
                    raise _fail(spec, found[0], found[1])
        elif spec.type is ValueType.URL:
            check_policy_url(spec, value)
        elif spec.format == "cidr_list":
            check_policy_cidrs(spec, value)
        elif spec.format == "host":
            problem = _host_problem(value.strip("[]"), True)
            if problem:
                raise _fail(spec, "blocked_host", f"host {problem}")
        return value


# ------------------------------------------------------------ seed specs

_S = ValueType
_AI = dict(section="ai", readers=("backend",))
_RATE = dict(section="rate_limits", readers=("backend",), reload_class=Reload.H)
_SSO = dict(section="sso", readers=("backend", "auth"), tier=Tier.T3)
_MAIL = dict(section="mail", readers=("backend", "auth"), tier=Tier.T3)
_KEYS = dict(is_secret=True, tier=Tier.T4, section="auth_keys")

SEED_SPECS: Tuple[SettingSpec, ...] = (
    SettingSpec(
        "AI_PROMPT_MAX_LENGTH",
        type=_S.INT,
        min_value=1,
        max_value=100000,
        default=4000,
        reload_class=Reload.H,
        description="Longest prompt accepted by the AI features.",
        **_AI,
    ),
    SettingSpec(
        "AI_DEFAULT_PROVIDER",
        type=_S.ENUM,
        choices=("openai", "anthropic", "compat"),
        tier=Tier.T2,
        description="Provider used when a request names none.",
        **_AI,
    ),
    SettingSpec(
        "AI_COMPAT_BASE_URL",
        type=_S.URL,
        tier=Tier.T3,
        description="Base URL of an OpenAI-compatible endpoint.",
        **_AI,
    ),
    SettingSpec(
        "API_FLOW_EVENTS_PER_WINDOW",
        type=_S.INT,
        min_value=1,
        max_value=100000,
        default=600,
        description="Flow events accepted per window.",
        **_RATE,
    ),
    SettingSpec(
        "API_FLOW_EVENTS_WINDOW_SECONDS",
        type=_S.INT,
        min_value=1,
        max_value=86400,
        default=60,
        description="Length of the flow event window.",
        **_RATE,
    ),
    SettingSpec(
        "API_PUBLIC_API_REQUESTS_PER_WINDOW",
        type=_S.INT,
        min_value=1,
        max_value=1000000,
        default=120,
        description="Public API requests per window.",
        **_RATE,
    ),
    SettingSpec(
        "API_EDITOR_OPS_SAVE_ENABLED",
        section="features",
        readers=("backend",),
        type=_S.BOOL,
        default=True,
        reload_class=Reload.H,
        description="Whether editor operations are saved server side.",
    ),
    SettingSpec(
        "API_FLOW_EVENTS_RETENTION_DAYS",
        section="retention",
        readers=("backend",),
        type=_S.INT,
        min_value=1,
        max_value=3650,
        default=90,
        tier=Tier.T2,
        description="Days flow events are kept.",
    ),
    SettingSpec(
        "API_TRUSTED_PROXIES",
        section="network",
        readers=("backend", "auth"),
        tier=Tier.T3,
        format="cidr_list",
        description="Comma separated proxy addresses whose forwarding headers are trusted.",
    ),
    SettingSpec(
        "SSO_ENABLED",
        type=_S.BOOL,
        default=False,
        description="Enables single sign-on.",
        **_SSO,
    ),
    SettingSpec(
        "SSO_POLIS_INTERNAL_URL",
        type=_S.URL,
        internal_ok=True,
        description="Address of the identity bridge on the internal network.",
        **_SSO,
    ),
    SettingSpec(
        "SSO_POLIS_API_KEY",
        is_secret=True,
        description="Key for the identity bridge API.",
        **_SSO,
    ),
    SettingSpec(
        "MAIL_SMTP_SERVER",
        format="host",
        description="Outgoing mail server host name.",
        **_MAIL,
    ),
    SettingSpec(
        "MAIL_SMTP_PORT",
        type=_S.INT,
        min_value=1,
        max_value=65535,
        default=587,
        description="Outgoing mail server port.",
        **_MAIL,
    ),
    SettingSpec(
        "MAIL_PASSWORD",
        is_secret=True,
        description="Outgoing mail account password.",
        **_MAIL,
    ),
    SettingSpec(
        "AUTH_JWT_SECRET",
        readers=("backend", "auth", "google"),
        description="Signs session tokens; rotated by a task, not edited.",
        **_KEYS,
    ),
    SettingSpec(
        "AUTH_AES_HEX_KEY",
        readers=("backend", "auth", "google"),
        description="Fernet key for state and secrets; rotated by a task.",
        **_KEYS,
    ),
    SettingSpec(
        "AUTH_INTERNAL_NOTIFY_KEY",
        readers=("backend", "auth"),
        description="Shared key for internal service calls; rotated by a task.",
        **_KEYS,
    ),
)


def default_registry(
    secret_problems: Optional[SecretCheck] = None,
    format_checks: Optional[Mapping[str, FormatCheck]] = None,
) -> Registry:
    """The full registry (``inventory.INVENTORY``). ``SEED_SPECS`` stays as the
    small fixed set the core library tests build their own registry from."""
    from .inventory import full_registry

    return full_registry(secret_problems, format_checks)
