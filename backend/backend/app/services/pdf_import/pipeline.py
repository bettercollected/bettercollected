"""Run an import's stages in order, checkpointing each on the import record.

A stage that already has a checkpoint is skipped, so a job that is retried
after a crash or a deploy resumes where it stopped. A refused document ends
the import with a message meant for the person who uploaded it; anything
unexpected ends it with a generic message (details go to the log, never the
document's content).
"""

from __future__ import annotations

import base64
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
    run_render,
    run_analysis,
    run_layout,
    run_text_layer,
)
from backend.app.services.pdf_import.storage import artifact_key
from backend.app.services.pdf_import.structuring import (
    merge,
    page_context,
    structure_page,
)

MESSAGE_FAILED = "The import failed unexpectedly. Please try again."
MESSAGE_UNAVAILABLE = "The document reader is unavailable. Please try again later."
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _checked_render(result: dict, number: int, max_bytes: int):
    """The sandbox's render of page ``number`` as (png, width, height), or None
    when the answer is not a plausible PNG of that page (untrusted output)."""
    pages = result.get("pages") if isinstance(result, dict) else None
    if not isinstance(pages, list) or len(pages) != 1 or not isinstance(pages[0], dict):
        return None
    page = pages[0]
    try:
        if int(page["number"]) != number:
            return None
        width, height = int(page["width_px"]), int(page["height_px"])
        encoded = page["png"]
        if not isinstance(encoded, str) or len(encoded) > max_bytes:
            return None
        png = base64.b64decode(encoded, validate=True)
    except (KeyError, TypeError, ValueError):
        return None
    if not png.startswith(PNG_SIGNATURE) or not (
        0 < width <= 10000 and 0 < height <= 10000
    ):
        return None
    return png, width, height


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class ImportPipeline:
    def __init__(self, repo, store, settings, provider_resolver=None):
        self._repo = repo
        self._store = store
        self._settings = settings
        # returns the AI provider for imports, or None (resolved per run)
        self._provider_resolver = provider_resolver

    def stages(
        self,
    ) -> List[Tuple[str, Callable[[FormImportDocument, bytes], Awaitable[dict]]]]:
        return [
            ("analyze", self._analyze),
            ("text", self._text),
            ("layout", self._layout),
            ("render", self._render),
            ("structure", self._structure),
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

    async def _render(self, record: FormImportDocument, data: bytes) -> dict:
        """Page images for the model and the review screen, stored next to the
        original. Native code: only through the isolated sandbox, one page per
        call so a heavy scan stays under the result cap on its own."""
        if not self._settings.SANDBOX_SOCKET:
            record.report.setdefault("notes", []).append(
                "Page images were not produced: the isolated document sandbox is not configured."
            )
            return {"skipped": "no isolated sandbox", "pages": []}
        numbers = [p.number for p in record.pages] or [1]
        stored, skipped = [], []
        for number in numbers:
            try:
                result = await run_render(
                    data,
                    record.content_type,
                    [number],
                    render_max_side=self._settings.RENDER_MAX_SIDE,
                    **self._limits(),
                )
            except DocumentRefused as refused:
                if refused.code != "too_complex":
                    raise
                skipped.append(number)
                continue
            image = _checked_render(result, number, self._settings.MAX_RESULT_BYTES)
            if image is None:
                skipped.append(number)
                continue
            png, width, height = image
            key = artifact_key(record.source_key, f"pages/{number}.png")
            await self._store.put(key, png, "image/png")
            stored.append(
                {"number": number, "key": key, "width_px": width, "height_px": height}
            )
        if skipped:
            record.report.setdefault("notes", []).append(
                f"{len(skipped)} page image(s) could not be produced."
            )
        return {"pages": stored, "skipped_pages": skipped}

    async def _load_json(self, record: FormImportDocument, name: str) -> dict:
        try:
            return json.loads(
                await self._store.get(artifact_key(record.source_key, name))
            )
        except Exception:  # noqa: BLE001 — a stage that did not run leaves no artifact
            return {"pages": []}

    async def _structure(self, record: FormImportDocument, data: bytes) -> dict:
        """The Form Document Model: one model call per page, grounded on the
        recovered words and layout items, merged across pages."""
        text = {
            p["number"]: p
            for p in (await self._load_json(record, "text.json"))["pages"]
        }
        layout = {
            p["number"]: p
            for p in (await self._load_json(record, "layout.json"))["pages"]
        }
        rendered = {
            p["number"]: p["key"]
            for p in (record.stages.get("render") or {}).get("pages", [])
        }
        provider = None
        if not record.ai_consent:
            # no consent for this import: nothing from the document goes to an
            # AI provider, only the deterministic structuring runs
            record.report.setdefault("notes", []).append(
                "AI structuring not used: no consent"
            )
        elif self._provider_resolver is not None:
            try:
                provider = self._provider_resolver()
            except (
                Exception
            ):  # noqa: BLE001 — no provider: deterministic structuring only
                provider = None
        results = []
        for page in record.pages or []:
            ctx = page_context(
                text.get(page.number), layout.get(page.number), page.number, page.route
            )
            image = None
            if page.number in rendered:
                try:
                    image = await self._store.get(rendered[page.number])
                except Exception:  # noqa: BLE001
                    image = None
            results.append(await structure_page(provider, ctx, image))
        fdm = merge(results)
        key = artifact_key(record.source_key, "fdm.json")
        await self._store.put(
            key, json.dumps(fdm, ensure_ascii=False).encode("utf-8"), "application/json"
        )
        questions = [e for e in fdm["elements"] if e["type"] == "question"]
        summary = {
            "questions": len(questions),
            "sections": sum(1 for e in fdm["elements"] if e["type"] == "section"),
            "statements": sum(1 for e in fdm["elements"] if e["type"] == "statement"),
            "staff_only": sum(1 for e in fdm["elements"] if e["type"] == "staff_only"),
            "pages": {str(p["number"]): p["source"] for p in fdm["pages"]},
            "warnings": sum(len(p["warnings"]) for p in fdm["pages"]),
        }
        record.report["structure"] = summary
        return {"artifact": key, **summary}

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
