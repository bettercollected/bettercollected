"""Repository of a workspace's reusable sections (Postgres only, new in 4.3).
Every read and write names the workspace: a section of another workspace is
never found."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.reusable_section import ReusableSectionDocument
from backend.db.models import WorkspaceLibrarySectionRow
from common.records.codec import row_values
from common.records.repository import RecordRepository

Row = WorkspaceLibrarySectionRow


def _id(value) -> str:
    return str(value)


class NameTaken(Exception):
    """A section of this workspace already has the name."""


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

    async def list_for_workspace(self, workspace_id) -> List[ReusableSectionDocument]:
        return await self.many(
            Row.workspace_id == _id(workspace_id), order_by=(Row.name_key, Row.id)
        )

    async def count_for_workspace(self, workspace_id) -> int:
        return await self.count(Row.workspace_id == _id(workspace_id))

    async def create(self, document: ReusableSectionDocument) -> ReusableSectionDocument:
        try:
            return await self.save_document(document)
        except IntegrityError as error:
            raise NameTaken() from error

    async def replace(
        self,
        document: ReusableSectionDocument,
        expected_version: Optional[int],
        *,
        bump: bool,
    ) -> ReusableSectionDocument:
        """Save a changed section in one locked step: the stored version must
        still be ``expected_version`` (when given), else ``VersionChanged`` and
        nothing is written. With ``bump`` the document's version (which the
        caller already raised) is written; otherwise the stored version stays
        (a rename)."""
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
            if expected_version is not None and current != expected_version:
                raise VersionChanged()
            if not bump:
                document.version = current
            document.touch()
            try:
                await session.execute(self._upsert_statement(row_values(document)))
            except IntegrityError as error:
                raise NameTaken() from error
        return document

    async def delete(self, workspace_id, section_id) -> int:
        return await self.delete_where(
            Row.id == _id(section_id), Row.workspace_id == _id(workspace_id)
        )

    async def delete_for_workspaces(self, workspace_ids) -> int:
        ids = [_id(w) for w in workspace_ids]
        if not ids:
            return 0
        return await self.delete_where(Row.workspace_id.in_(ids))
