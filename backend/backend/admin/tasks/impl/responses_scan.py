"""Count stored response values that carry the ciphertext prefix but do not
decrypt. Read-only. The core of the ``responses.check_undecryptable`` task and
of ``scripts/check_undecryptable_values.py``.

Until ``CryptoService.encrypt`` stopped passing it through, a plaintext
starting with ``v1:`` (the ciphertext prefix) was stored as is, unencrypted.
Such a value looks like ciphertext and does not decrypt. Checked on each
response (``form_responses``): ``answers``, ``hidden_fields``,
``internal_answers`` and every ``respondent_feedback`` message. Each value is
tried under its response's workspace, or under every workspace the form is
linked to when the response has none (stored before workspaces were stamped).

Reports counts per store and field. Never ids, values or plaintext; never
writes.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple

from backend.admin.tasks.impl.responses_common import (
    CIPHERTEXT_PREFIX,
    Opener,
    PostgresBase,
    load_keyset,
    make_opener,
)

FIELDS = ("answers", "hidden_fields", "internal_answers")
FEEDBACK = "respondent_feedback.message"

# called after each batch with (store name, responses seen so far in the store);
# True stops the scan (cancel)
OnBatch = Callable[[str, int], Awaitable[bool]]


def default_opener() -> Opener:
    """``opens(workspace_id, form_id, value)`` under the loaded keyset."""
    keyset = load_keyset()
    if keyset is None:
        raise RuntimeError("MASTER_ENCRYPTION_KEYSET is not set")
    return make_opener(keyset)


def _prefixed(value: Any) -> Optional[bytes]:
    if isinstance(value, (bytes, bytearray)) and bytes(value).startswith(
        CIPHERTEXT_PREFIX
    ):
        return bytes(value)
    return None


def _looks_like_text(value: bytes) -> bool:
    try:
        text = value[len(CIPHERTEXT_PREFIX) :].decode("utf-8")
    except UnicodeDecodeError:
        return False
    return all(c.isprintable() or c in "\n\r\t" for c in text)


def values_of(record: Dict[str, Any]) -> Iterable[Tuple[str, Any]]:
    """(field, stored value) of each encrypted value of one response."""
    for field in FIELDS:
        yield field, record.get(field)
    for entry in record.get("respondent_feedback") or []:
        if isinstance(entry, dict):
            yield FEEDBACK, entry.get("message")


def check_record(
    record: Dict[str, Any],
    links: Dict[str, List[str]],
    opens: Opener,
    counts: Dict[str, Counter],
) -> None:
    form_id = str(record.get("form_id"))
    workspace = record.get("workspace_id")
    candidates = [str(workspace)] if workspace else links.get(form_id) or []
    for field, raw in values_of(record):
        value = _prefixed(raw)
        if value is None:
            continue
        tally = counts[field]
        tally["prefixed"] += 1
        if not candidates:
            tally["no_workspace_to_try"] += 1
            continue
        if any(opens(w, form_id, value) for w in candidates):
            tally["decrypts"] += 1
            continue
        tally["does_not_decrypt"] += 1
        tally["of_which_text" if _looks_like_text(value) else "of_which_binary"] += 1


# --------------------------------------------------------------------- stores
class PostgresStore(PostgresBase):
    async def batch(self, after, limit: int) -> List[dict]:
        from sqlalchemy import select, text

        from backend.db.models import FormResponseRow as row
        from common.db.canonical import from_canonical_document

        keys = (*FIELDS, "respondent_feedback")
        stmt = select(
            row.id, row.form_id, row.workspace_id, *(row.doc[k] for k in keys)
        )
        if after is not None:
            stmt = stmt.where(row.id > after)
        stmt = stmt.order_by(row.id).limit(limit)
        records = []
        async with self.engine.connect() as conn:
            await conn.execute(text("SET TRANSACTION READ ONLY"))
            for values in await conn.execute(stmt):
                stored = {k: v for k, v in zip(keys, values[3:]) if v is not None}
                records.append(
                    {
                        "key": values[0],
                        "form_id": values[1],
                        "workspace_id": values[2],
                        **from_canonical_document(stored),
                    }
                )
        return records


STORE_CLASSES = {"postgres": PostgresStore}


# ------------------------------------------------------------------------ run
async def check_store(
    store,
    opens: Opener,
    batch_size: int = 500,
    on_batch: Optional[OnBatch] = None,
) -> Dict[str, Any]:
    links = await store.links()
    counts: Dict[str, Counter] = defaultdict(Counter)
    responses = 0
    complete = True
    after = None
    while True:
        batch = await store.batch(after, batch_size)
        if not batch:
            break
        after = batch[-1]["key"]
        for record in batch:
            responses += 1
            check_record(record, links, opens, counts)
        if on_batch is not None and await on_batch(store.name, responses):
            complete = False
            break
    report = {
        "responses": responses,
        "fields": {field: dict(tally) for field, tally in sorted(counts.items())},
        "does_not_decrypt": sum(t["does_not_decrypt"] for t in counts.values()),
    }
    if not complete:
        report["complete"] = False
    return report


async def run(
    stores,
    opens: Opener,
    batch_size: int = 500,
    on_batch: Optional[OnBatch] = None,
) -> Dict[str, Any]:
    report: Dict[str, Any] = {"stores": {}}
    for store in stores:
        report["stores"][store.name] = await check_store(
            store, opens, batch_size, on_batch
        )
        if report["stores"][store.name].get("complete") is False:
            break
    return report
