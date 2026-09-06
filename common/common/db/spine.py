"""Typed spine columns generated from ``doc`` (decision D2).

    S = SpineColumns("app")

    class FormRow(Base, BaseRow):
        __tablename__ = "forms"
        form_id = S.text("form_id")
        custom_url = S.text("settings", "custom_url")      # nested path
        published_at = S.ts("published_at")
        is_default = S.bool("default", name="is_default")  # rename reserved words

Each becomes ``GENERATED ALWAYS AS (<schema>.bc_<type>(doc -> 'key')) STORED``,
so the application writes ``doc`` alone and a spine value can never disagree
with the document it was derived from. Generated columns can be indexed and
carry unique constraints like any other.
"""

from __future__ import annotations

import re

from sqlalchemy import BigInteger, Boolean, Computed, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import mapped_column

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class SpineColumns:
    def __init__(self, schema: str):
        if not schema.isidentifier() or not schema.islower():
            raise ValueError(
                f"schema must be a plain lowercase identifier, got {schema!r}"
            )
        self.schema = schema

    @staticmethod
    def _source(path: tuple[str, ...]) -> str:
        if not path:
            raise ValueError("a spine column needs at least one key")
        for key in path:
            if not _KEY.match(key):
                raise ValueError(f"unsafe document key {key!r}")
        if len(path) == 1:
            return f"doc -> '{path[0]}'"
        return "doc #> '{" + ",".join(path) + "}'"

    def _column(self, sqltype, function: str, path: tuple[str, ...], name: str | None):
        expression = f"{self.schema}.{function}({self._source(path)})"
        computed = Computed(expression, persisted=True)
        if name is not None:
            return mapped_column(name, sqltype, computed, nullable=True)
        return mapped_column(sqltype, computed, nullable=True)

    def text(self, *path: str, name: str | None = None):
        return self._column(Text, "bc_text", path, name)

    def ts(self, *path: str, name: str | None = None):
        return self._column(TIMESTAMP(timezone=True), "bc_ts", path, name)

    def bool(self, *path: str, name: str | None = None):
        return self._column(Boolean, "bc_bool", path, name)

    def int(self, *path: str, name: str | None = None):
        return self._column(BigInteger, "bc_int", path, name)
