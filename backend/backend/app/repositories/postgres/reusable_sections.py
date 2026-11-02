"""Repository of a workspace's reusable sections (Postgres only, new in 4.3).
Every read and write names the workspace: a section of another workspace is
never found."""

from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.reusable_section import ReusableSectionDocument
from backend.db.models import WorkspaceLibrarySectionRow
from common.records.codec import decode, row_values
from common.records.repository import RecordRepository

Row = WorkspaceLibrarySectionRow


def _id(value) -> str:
    return str(value)


class NameTaken(Exception):
    """A section of this workspace already has the name."""


class LimitReached(Exception):
    """The workspace already holds as many sections as it may."""


class VersionChanged(Exception):
    """Another editor saved the section since it was read."""


class PostgresReusableSectionRepository(RecordRepository):
    row = Row
    document = ReusableSectionDocument

    async def get(self, workspace_id, section_id) -> Optional[ReusableSectionDocument]:
        """Only a section of this workspace."""
        return await self.one(
            Row.id == _id(section_id), Row.workspace_id == _id(workspace_id)
        )

    async def list_summaries(self, workspace_id) -> List[Dict[str, Any]]:
        """The list's columns only (name, description, version, question count,
        updated_at), read by key: never the questions or the history."""
        async with self._session() as session:
            rows = (
                await session.execute(
                    select(
                        Row.id,
                        Row.doc["name"].astext,
                        Row.doc["description"].astext,
                        Row.doc["version"].astext,
                        Row.doc["question_count"].astext,
                        Row.updated_at,
                    )
                    .where(Row.workspace_id == _id(workspace_id))
                    .order_by(Row.name_key, Row.id)
                )
            ).all()
        return [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "version": int(r[3] or 1),
                "question_count": int(r[4] or 0),
                "updated_at": r[5],
            }
            for r in rows
        ]

    async def content_bytes(self, workspace_id) -> int:
        """What the workspace's sections take (the stored documents, history
        included), for the workspace-wide budget."""
        async with self._session() as session:
            total = (
                await session.execute(
                    select(func.coalesce(func.sum(func.octet_length(text("doc::text"))), 0)).where(
                        Row.workspace_id == _id(workspace_id)
                    )
                )
            ).scalar_one()
        return int(total or 0)

    async def create(
        self, document: ReusableSectionDocument, max_count: Optional[int] = None
    ) -> ReusableSectionDocument:
        """Insert a section. With ``max_count`` the count and the insert are one
        step under a lock on the workspace, so two saves cannot both pass the
        limit (``LimitReached``)."""
        self._check_collection(document, Row)
        try:
            async with self._session() as session, session.begin():
                if max_count is not None:
                    await session.execute(
                        text("select pg_advisory_xact_lock(hashtext(:key))"),
                        {"key": "library_sections:" + _id(document.workspace_id)},
                    )
                    held = (
                        await session.execute(
                            select(func.count()).select_from(Row).where(
                                Row.workspace_id == _id(document.workspace_id)
                            )
                        )
                    ).scalar_one()
                    if held >= max_count:
                        raise LimitReached()
                await session.execute(self._upsert_statement(row_values(document)))
        except IntegrityError as error:
            raise NameTaken() from error
        return document

    async def replace(
        self,
        document: ReusableSectionDocument,
        expected_version: Optional[int],
        *,
        bump: bool,
    ) -> ReusableSectionDocument:
        """Save a changed section in one locked step.

        ``bump``: a new version. The stored version must still be
        ``expected_version`` (else ``VersionChanged``, nothing written) and the
        caller's whole document is written.

        Not ``bump`` (a rename): only the name, its key, the description and who
        changed it are taken from ``document`` and merged onto the row **as it is
        locked now**, so a content save that landed since the caller read it is
        never overwritten and the version never moves."""
        self._check_collection(document, Row)
        async with self._session() as session, session.begin():
            stored = (
                await session.execute(
                    select(Row.doc)
                    .where(
                        Row.id == _id(document.id),
                        Row.workspace_id == _id(document.workspace_id),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if stored is None:
                raise LookupError("no such section")
            current = int(stored.get("version") or 1)
            if bump:
                if expected_version is not None and current != expected_version:
                    raise VersionChanged()
                target = document
            else:
                target = decode(self.document, stored)
                target.name = document.name
                target.name_key = document.name_key
                target.description = document.description
                target.updated_by = document.updated_by
            target.touch()
            try:
                await session.execute(self._upsert_statement(row_values(target)))
            except IntegrityError as error:
                raise NameTaken() from error
        return target

    async def delete(self, workspace_id, section_id) -> int:
        return await self.delete_where(
            Row.id == _id(section_id), Row.workspace_id == _id(workspace_id)
        )

    async def delete_for_workspaces(self, workspace_ids) -> int:
        ids = [_id(w) for w in workspace_ids]
        if not ids:
            return 0
        return await self.delete_where(Row.workspace_id.in_(ids))
