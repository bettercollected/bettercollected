"""Run an import's stages in order, checkpointing each on the import record.

A stage that already has a checkpoint is skipped, so a job that is retried
after a crash or a deploy resumes where it stopped. A refused document ends
the import with a message meant for the person who uploaded it; anything
unexpected ends it with a generic message (details go to the log, never the
document's content).
"""

from __future__ import annotations

import collections
import datetime as dt
import json
from typing import Awaitable, Callable, List, Tuple

from beanie import PydanticObjectId
from loguru import logger

from backend.app.schemas.form_import import (
    FormImportDocument,
    ImportStatus,
    PageAnalysis,
)
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.sandbox import (
    SandboxUnavailable,
    run_analysis,
    run_layout,
    run_text_layer,
)
from backend.app.services.pdf_import.storage import artifact_key

MESSAGE_FAILED = "The import failed unexpectedly. Please try again."
MESSAGE_UNAVAILABLE = "The document reader is unavailable. Please try again later."


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class ImportPipeline:
    def __init__(self, repo, store, settings):
        self._repo = repo
        self._store = store
        self._settings = settings

    def stages(
        self,
    ) -> List[Tuple[str, Callable[[FormImportDocument, bytes], Awaitable[dict]]]]:
        return [
            ("analyze", self._analyze),
            ("text", self._text),
            ("layout", self._layout),
        ]

    async def _analyze(self, record: FormImportDocument, data: bytes) -> dict:
        result = await run_analysis(data, record.content_type, **self._limits())
        record.page_count = result["page_count"]
        record.pages = [PageAnalysis(**page) for page in result["pages"]]
        record.report["routes"] = result["routes"]
        if result.get("xfa"):
            record.report.setdefault("notes", []).append(
                "The PDF uses XFA forms; its pages are read from their images."
            )
        return {"page_count": result["page_count"], "routes": result["routes"]}

    def _limits(self) -> dict:
        s = self._settings
        return dict(
            max_pages=s.MAX_PAGES,
            max_pixels=s.MAX_IMAGE_PIXELS,
            timeout_s=s.SANDBOX_TIMEOUT_S,
            memory_mb=s.SANDBOX_MEMORY_MB,
            max_parallel=s.MAX_PARALLEL_SANDBOXES,
            max_result_bytes=s.MAX_RESULT_BYTES,
            socket_path=s.SANDBOX_SOCKET,
            require_isolated=s.REQUIRE_ISOLATED_SANDBOX,
        )

    async def _text(self, record: FormImportDocument, data: bytes) -> dict:
        """The text layer of every page that has one, stored as an artifact next
        to the original. Pages whose recovered text cannot be trusted enough
        switch to being read from their image."""
        if record.content_type != "application/pdf":
            return {"skipped": "image upload: no text layer", "words": 0}
        skip = [p.number for p in record.pages if p.route == "scan"]
        result = await run_text_layer(data, skip_pages=skip, **self._limits())
        key = artifact_key(record.source_key, "text.json")
        await self._store.put(
            key,
            json.dumps(result, ensure_ascii=False).encode("utf-8"),
            "application/json",
        )
        by_number = {p.number: p for p in record.pages}
        words = decoded = untrusted = 0
        switched = []
        for page in result["pages"]:
            if page.get("skipped"):
                continue
            words += len(page["words"])
            decoded += sum(1 for w in page["words"] if w["source"] == "decoded")
            untrusted += page.get("untrusted_words", 0)
            analysed = by_number.get(page["number"])
            if (
                analysed is not None
                and page.get("read_from_image")
                and analysed.route == "text"
            ):
                analysed.route = "vision"
                analysed.reasons = analysed.reasons + [
                    "recovered text not reliable enough"
                ]
                switched.append(page["number"])
        record.report["routes"] = dict(
            collections.Counter(p.route for p in record.pages)
        )
        record.report["text"] = {
            "words": words,
            "decoded_words": decoded,
            "untrusted_words": untrusted,
        }
        return {
            "artifact": key,
            "words": words,
            "decoded_words": decoded,
            "untrusted_words": untrusted,
            "switched_to_image": switched,
        }

    async def _layout(self, record: FormImportDocument, data: bytes) -> dict:
        """Layout primitives of the pages read from their drawing (the image
        routes get theirs from the vision stage), stored next to the original."""
        if record.content_type != "application/pdf":
            return {"skipped": "image upload: no drawing", "primitives": 0}
        skip = [p.number for p in record.pages if p.route in ("scan", "vision")]
        result = await run_layout(data, skip_pages=skip, **self._limits())
        key = artifact_key(record.source_key, "layout.json")
        await self._store.put(
            key,
            json.dumps(result, ensure_ascii=False).encode("utf-8"),
            "application/json",
        )
        totals: dict = {}
        for page in result["pages"]:
            for kind, n in page.get("counts", {}).items():
                totals[kind] = totals.get(kind, 0) + n
        record.report["layout"] = totals
        return {"artifact": key, "primitives": sum(totals.values()), "counts": totals}

    async def give_up(self, import_id: PydanticObjectId) -> FormImportDocument:
        """Retries are exhausted: the sandbox stayed unreachable. Fail the
        import so it no longer holds the workspace's import slot."""
        record = await self._repo.get(import_id)
        if record is None or record.status in (
            ImportStatus.COMPLETED,
            ImportStatus.FAILED,
        ):
            return record
        record.status = ImportStatus.FAILED
        record.error = MESSAGE_UNAVAILABLE
        record.report["refused"] = "unavailable"
        record.finished_at = _now()
        await self._repo.save(record)
        logger.error("form import {} gave up waiting for the sandbox", import_id)
        return record

    async def run(self, import_id: PydanticObjectId) -> FormImportDocument:
        record = await self._repo.get(import_id)
        if record is None or record.status in (
            ImportStatus.COMPLETED,
            ImportStatus.FAILED,
        ):
            return record
        record.status = ImportStatus.RUNNING
        record.started_at = record.started_at or _now()
        record.error = None
        await self._repo.save(record)
        data = None
        try:
            for name, stage in self.stages():
                if name in record.stages:
                    continue
                record.stage = name
                await self._repo.save(record)
                if data is None:
                    data = await self._store.get(record.source_key)
                record.stages[name] = {
                    "finished_at": _now().isoformat(),
                    **(await stage(record, data)),
                }
                await self._repo.save(record)
            record.status = ImportStatus.COMPLETED
            record.stage = None
        except DocumentRefused as refused:
            record.status = ImportStatus.FAILED
            record.error = refused.message
            record.report["refused"] = refused.code
            logger.info("form import {} refused: {}", record.id, refused.code)
        except SandboxUnavailable as unavailable:
            # the sandbox, not the document: the job retries; checkpoints keep progress
            record.status = ImportStatus.QUEUED
            record.error = "Waiting for the document reader to become available."
            logger.warning(
                "form import {} waiting for the sandbox: {}", record.id, unavailable
            )
            await self._repo.save(record)
            raise
        except (
            Exception
        ):  # noqa: BLE001 — reported on the record, logged without content
            record.status = ImportStatus.FAILED
            record.error = MESSAGE_FAILED
            logger.exception(
                "form import {} failed at stage {}", record.id, record.stage
            )
        record.finished_at = _now()
        await self._repo.save(record)
        return record
