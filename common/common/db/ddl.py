"""Per-schema SQL helper functions that spine columns are generated from.

Every migrated table keeps the whole document in ``doc`` (BSON Extended JSON)
and derives its typed "spine" columns from it with ``GENERATED ALWAYS AS (...)
STORED`` expressions. Those expressions may only call IMMUTABLE functions, so
the extraction lives in four small SQL functions created in each service's
schema by its first migration:

    bc_text(v)  string / number / boolean as text; ``{"$oid": ...}``,
                ``{"$numberLong": ...}``, ``{"$numberDecimal": ...}`` unwrapped
    bc_ts(v)    ``{"$date": "...Z"}``, ``{"$date": {"$numberLong": ms}}`` or a
                bare ISO-8601 string (form_responses stores those); strings
                without an offset are taken as UTC, so the result never depends
                on the session time zone — which is what makes it IMMUTABLE
    bc_bool(v)  boolean, or the strings "true"/"false"
    bc_int(v)   number (truncated), ``{"$numberLong": ...}`` or a digit string

All return NULL for NULL / absent / other-typed input rather than raising, so
a document with an unexpected shape lands as a row with a NULL spine value and
is caught by verification instead of breaking a write.
"""

from __future__ import annotations

HELPER_FUNCTIONS = ("bc_text", "bc_ts", "bc_bool", "bc_int")

_TEXT = """
CREATE OR REPLACE FUNCTION {schema}.bc_text(v jsonb) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE RETURNS NULL ON NULL INPUT AS $$
    SELECT CASE jsonb_typeof(v)
        WHEN 'string'  THEN v #>> '{{}}'
        WHEN 'number'  THEN v #>> '{{}}'
        WHEN 'boolean' THEN v #>> '{{}}'
        WHEN 'object'  THEN COALESCE(v ->> '$oid', v ->> '$numberLong', v ->> '$numberDecimal')
        ELSE NULL
    END
$$;
"""

_TS = r"""
CREATE OR REPLACE FUNCTION {schema}.bc_ts(v jsonb) RETURNS timestamptz
LANGUAGE sql IMMUTABLE PARALLEL SAFE RETURNS NULL ON NULL INPUT AS $$
    SELECT CASE
        WHEN jsonb_typeof(v) = 'object' AND jsonb_typeof(v -> '$date') = 'string'
            THEN (v ->> '$date')::timestamptz
        WHEN jsonb_typeof(v) = 'object' AND jsonb_typeof(v -> '$date') = 'object'
            THEN to_timestamp(((v -> '$date' ->> '$numberLong')::bigint) / 1000.0)
        WHEN jsonb_typeof(v) = 'string' AND (v #>> '{{}}') ~ '(Z|[+-]\d\d:?\d\d)$'
            THEN (v #>> '{{}}')::timestamptz
        WHEN jsonb_typeof(v) = 'string' AND (v #>> '{{}}') ~ '^\d{{4}}-\d\d-\d\d'
            THEN ((v #>> '{{}}')::timestamp AT TIME ZONE 'UTC')
        ELSE NULL
    END
$$;
"""

_BOOL = """
CREATE OR REPLACE FUNCTION {schema}.bc_bool(v jsonb) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE RETURNS NULL ON NULL INPUT AS $$
    SELECT CASE jsonb_typeof(v)
        WHEN 'boolean' THEN (v #>> '{{}}')::boolean
        WHEN 'string'  THEN CASE lower(v #>> '{{}}') WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END
        ELSE NULL
    END
$$;
"""

_INT = r"""
CREATE OR REPLACE FUNCTION {schema}.bc_int(v jsonb) RETURNS bigint
LANGUAGE sql IMMUTABLE PARALLEL SAFE RETURNS NULL ON NULL INPUT AS $$
    SELECT CASE jsonb_typeof(v)
        WHEN 'number' THEN trunc((v #>> '{{}}')::numeric)::bigint
        WHEN 'object' THEN (v ->> '$numberLong')::bigint
        WHEN 'string' THEN CASE WHEN (v #>> '{{}}') ~ '^-?\d+$' THEN (v #>> '{{}}')::bigint ELSE NULL END
        ELSE NULL
    END
$$;
"""


def _check_schema(schema: str) -> None:
    if not schema.isidentifier() or not schema.islower():
        raise ValueError(f"schema must be a plain lowercase identifier, got {schema!r}")


def helper_function_ddl(schema: str) -> list[str]:
    """The CREATE statements for ``schema``, in dependency-free order."""
    _check_schema(schema)
    return [tpl.format(schema=schema).strip() for tpl in (_TEXT, _TS, _BOOL, _INT)]


def drop_helper_function_ddl(schema: str) -> list[str]:
    _check_schema(schema)
    return [
        f"DROP FUNCTION IF EXISTS {schema}.{name}(jsonb)" for name in HELPER_FUNCTIONS
    ]
