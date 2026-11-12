"""Which questions of a form one caller may use in a report: the seam that
field-level access plugs into.

``ReportFieldPolicy.visible_fields`` is asked once per request, for every
question key the form has (reportable or not), and answers the keys the caller
may use as a measure, a dimension *and* a filter. Everything the report builds
(the catalogue, the validation of a definition, the cached aggregates) goes
through it: a question that is not visible is refused exactly like one that does
not exist (``definition.UNKNOWN_FIELD``), so the answer never says that a hidden
question is there.

Today it allows every question: a member who may read the form's responses sees
every answer, so a report may use every reportable question. When field-level
access is built, the body of ``visible_fields`` becomes its rule; nothing else
in the reporting package changes. ``fingerprint`` is part of the cache key, so
two members whose views differ never share an aggregate.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, FrozenSet

from common.ids import RecordId
from common.models.user import User


class ReportFieldPolicy:
    async def visible_fields(
        self,
        user: User,
        workspace_id: RecordId,
        form_id: str,
        question_keys: Iterable[str],
    ) -> FrozenSet[str]:
        """The question keys (``q:<id>``) among ``question_keys`` that ``user``
        may use in a report of this form."""
        return frozenset(question_keys)

    @staticmethod
    def fingerprint(visible: Iterable[str]) -> str:
        """A short digest of the visible set (a cache key part)."""
        digest = hashlib.sha256("\n".join(sorted(visible)).encode()).hexdigest()
        return digest[:16]
