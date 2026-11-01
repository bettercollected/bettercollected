"""Repository of a workspace's option lists (Postgres only, new in 4.3). Every
read and write names the workspace: a list of another workspace is never
found."""

from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.option_list import OptionListDocument
from backend.db.models import WorkspaceOptionListRow
from common.records.codec import row_values
from common.records.repository import RecordRepository

Row = WorkspaceOptionListRow


def _id(value) -> str:
    return str(value)


class NameTaken(Exception):
    """A list of this workspace already has the name."""


class RevisionChanged(Exception):
    """Another editor saved the list since it was read."""


class PostgresOptionListRepository(RecordRepository):
    row = Row
    document = OptionListDocument

    async def get(self, workspace_id, list_id) -> Optional[OptionListDocument]:
        """Only a list of this workspace."""
        return await self.one(
            Row.id == _id(list_id), Row.workspace_id == _id(workspace_id)
        )

    async def revision(self, workspace_id, list_id) -> Optional[int]:
        """The list's revision without reading its items (the cache token)."""
        async with self._session() as session:
            found = (
                await session.execute(
                    select(text("(doc ->> 'revision')::int"))
                    .select_from(Row)
                    .where(
                        Row.id == _id(list_id), Row.workspace_id == _id(workspace_id)
                    )
                )
            ).scalar_one_or_none()
        return found

    async def list_for_workspace(self, workspace_id) -> List[OptionListDocument]:
        return await self.many(
            Row.workspace_id == _id(workspace_id), order_by=(Row.name_key, Row.id)
        )

    async def count_for_workspace(self, workspace_id) -> int:
        return await self.count(Row.workspace_id == _id(workspace_id))

    async def create(self, document: OptionListDocument) -> OptionListDocument:
        try:
            return await self.save_document(document)
        except IntegrityError as error:
            raise NameTaken() from error

    async def replace(
        self, document: OptionListDocument, expected_revision: Optional[int]
    ) -> OptionListDocument:
        """Save a changed list in one locked step: the stored revision must
        still be ``expected_revision`` (when given), else ``RevisionChanged``
        and nothing is written; the revision goes up by one."""
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
                raise LookupError("no such list")
            current = int(stored.get("revision") or 1)
            if expected_revision is not None and current != expected_revision:
                raise RevisionChanged()
            document.revision = current + 1
            document.touch()
            try:
                await session.execute(self._upsert_statement(row_values(document)))
            except IntegrityError as error:
                raise NameTaken() from error
        return document

    async def delete(self, workspace_id, list_id) -> int:
        return await self.delete_where(
            Row.id == _id(list_id), Row.workspace_id == _id(workspace_id)
        )

    async def delete_for_workspace(self, workspace_id) -> int:
        return await self.delete_where(Row.workspace_id == _id(workspace_id))


class PostgresOptionListUsage(RecordRepository):
    """Which forms of a workspace take their options from which list: the
    draft of every form and its latest published version are searched for
    ``optionSource.listId`` (stored camelCase; the snake_case spelling too), one
    read, no answer touched."""

    row = Row
    document = OptionListDocument

    _SQL = text("""
        WITH mine AS (
            SELECT w.form_id AS form_id
            FROM app.workspace_forms w
            WHERE w.workspace_id = :workspace_id
        ),
        latest AS (
            SELECT DISTINCT ON (v.form_id) v.form_id, v.doc
            FROM app.form_versions v
            JOIN mine ON mine.form_id = v.form_id
            ORDER BY v.form_id, v.version DESC
        ),
        docs AS (
            SELECT f.form_id AS form_id, f.title AS title, f.doc AS doc
            FROM app.forms f JOIN mine ON mine.form_id = f.form_id
            UNION ALL
            SELECT l.form_id, l.doc ->> 'title', l.doc FROM latest l
        )
        SELECT DISTINCT docs.form_id, docs.title, found #>> '{}' AS list_id
        FROM docs,
             LATERAL (
                 SELECT * FROM jsonb_path_query(docs.doc, '$.**.optionSource.listId')
                 UNION ALL
                 SELECT * FROM jsonb_path_query(docs.doc, '$.**.option_source.list_id')
             ) AS found(found)
        """)

    async def forms_by_list(
        self, workspace_id
    ) -> Dict[str, List[Tuple[str, Optional[str]]]]:
        """``{list id: [(form id, title)]}`` of the forms that use a list."""
        async with self._session() as session:
            rows = (
                await session.execute(self._SQL, {"workspace_id": _id(workspace_id)})
            ).all()
        usage: Dict[str, List[Tuple[str, Optional[str]]]] = {}
        seen = set()
        for form_id, title, list_id in rows:
            if not list_id or (list_id, form_id) in seen:
                continue
            seen.add((list_id, form_id))
            usage.setdefault(list_id, []).append((form_id, title))
        return usage
