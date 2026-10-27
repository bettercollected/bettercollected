"""Repositories of the registration feature (Postgres only, new in 4.2):
services, form registrations and deliveries. Queries use the spine columns of
:mod:`backend.db.models`. A delivery row never holds answer data."""

import datetime as dt
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.registration import (
    DeliveryStatus,
    FormRegistrationDocument,
    RegistrationDeliveryDocument,
    RegistrationServiceDocument,
)
from backend.db.models import (
    FormRegistrationRow,
    RegistrationDeliveryRow,
    RegistrationServiceRow,
)
from common.records.codec import decode, row_values
from common.records.repository import RecordRepository


class ServiceNameTaken(Exception):
    """The workspace already has a service with this name."""


def _id(value) -> str:
    return str(value)


class PostgresRegistrationServiceRepository(RecordRepository):
    row = RegistrationServiceRow
    document = RegistrationServiceDocument

    async def create(
        self, document: RegistrationServiceDocument
    ) -> RegistrationServiceDocument:
        try:
            return await self.upsert(document)
        except IntegrityError:
            raise ServiceNameTaken(document.name)

    async def save(
        self, document: RegistrationServiceDocument
    ) -> RegistrationServiceDocument:
        try:
            return await self.save_document(document)
        except IntegrityError:
            raise ServiceNameTaken(document.name)

    async def get(
        self, workspace_id, service_id
    ) -> Optional[RegistrationServiceDocument]:
        """Only a service of this workspace."""
        return await self.one(
            RegistrationServiceRow.id == _id(service_id),
            RegistrationServiceRow.workspace_id == _id(workspace_id),
        )

    async def list_by_workspace(
        self, workspace_id
    ) -> List[RegistrationServiceDocument]:
        return await self.many(
            RegistrationServiceRow.workspace_id == _id(workspace_id),
            order_by=(RegistrationServiceRow.name, RegistrationServiceRow.id),
        )

    async def delete(self, workspace_id, service_id) -> int:
        return await self.delete_where(
            RegistrationServiceRow.id == _id(service_id),
            RegistrationServiceRow.workspace_id == _id(workspace_id),
        )

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        return await self.delete_where(
            RegistrationServiceRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )


class PostgresFormRegistrationRepository(RecordRepository):
    row = FormRegistrationRow
    document = FormRegistrationDocument

    async def get_for_form(
        self, workspace_id, form_id
    ) -> Optional[FormRegistrationDocument]:
        return await self.one(
            FormRegistrationRow.workspace_id == _id(workspace_id),
            FormRegistrationRow.form_id == _id(form_id),
        )

    async def get(self, registration_id) -> Optional[FormRegistrationDocument]:
        return await self.one(FormRegistrationRow.id == _id(registration_id))

    async def save(
        self, document: FormRegistrationDocument
    ) -> FormRegistrationDocument:
        return await self.save_document(document)

    async def count_for_service(self, service_id) -> int:
        return await self.count(FormRegistrationRow.service_id == _id(service_id))

    async def list_all(
        self, limit: int, after_id: str = ""
    ) -> List[FormRegistrationDocument]:
        return await self.many(
            FormRegistrationRow.id > after_id,
            order_by=(FormRegistrationRow.id,),
            limit=limit,
        )

    async def delete(self, registration_id) -> int:
        return await self.delete_where(FormRegistrationRow.id == _id(registration_id))

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        return await self.delete_where(
            FormRegistrationRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )


class PostgresRegistrationDeliveryRepository(RecordRepository):
    row = RegistrationDeliveryRow
    document = RegistrationDeliveryDocument

    async def create_if_absent(
        self, document: RegistrationDeliveryDocument
    ) -> Optional[RegistrationDeliveryDocument]:
        """Insert unless this registration already has a delivery for the
        response (the idempotency key): the document, or None when one exists."""
        document.ensure_id()
        values = row_values(document)
        names = self._column_names()
        async with self._session() as session, session.begin():
            result = await session.execute(
                pg_insert(self.row)
                .values({names[k]: v for k, v in values.items()})
                .on_conflict_do_nothing()
                .returning(self.row.id)
            )
            inserted = result.first() is not None
        return document if inserted else None

    async def get(self, delivery_id) -> Optional[RegistrationDeliveryDocument]:
        return await self.one(RegistrationDeliveryRow.id == _id(delivery_id))

    async def get_in_form(
        self, workspace_id, form_id, delivery_id
    ) -> Optional[RegistrationDeliveryDocument]:
        return await self.one(
            RegistrationDeliveryRow.id == _id(delivery_id),
            RegistrationDeliveryRow.workspace_id == _id(workspace_id),
            RegistrationDeliveryRow.form_id == _id(form_id),
        )

    async def save(
        self, document: RegistrationDeliveryDocument
    ) -> RegistrationDeliveryDocument:
        return await self.save_document(document)

    async def claim(
        self, delivery_id, allowed: Iterable[DeliveryStatus], *, now: dt.datetime
    ) -> Optional[RegistrationDeliveryDocument]:
        """Atomically move a delivery that is in one of ``allowed`` to
        ``in_progress`` (one attempt more); None when it is in another state,
        i.e. delivered, failed, or being handled by another job."""
        statuses = [s.value for s in allowed]
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(self.row.doc)
                    .where(
                        RegistrationDeliveryRow.id == _id(delivery_id),
                        RegistrationDeliveryRow.status.in_(statuses),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            claimed = decode(self.document, doc)
            claimed.status = DeliveryStatus.IN_PROGRESS
            claimed.attempts += 1
            claimed.last_attempt_at = now
            claimed.touch()
            await session.execute(self._upsert_statement(row_values(claimed)))
        return claimed

    async def list_for_form(
        self,
        workspace_id,
        form_id,
        *,
        statuses: Optional[Sequence[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RegistrationDeliveryDocument]:
        where = [
            RegistrationDeliveryRow.workspace_id == _id(workspace_id),
            RegistrationDeliveryRow.form_id == _id(form_id),
        ]
        if statuses:
            where.append(RegistrationDeliveryRow.status.in_(list(statuses)))
        async with self._session() as session:
            docs = (
                (
                    await session.execute(
                        select(self.row.doc)
                        .where(*where)
                        .order_by(
                            RegistrationDeliveryRow.created_at.desc(),
                            RegistrationDeliveryRow.id.desc(),
                        )
                        .limit(limit)
                        .offset(offset)
                    )
                )
                .scalars()
                .all()
            )
        return [decode(self.document, d) for d in docs]

    async def count_for_form(self, workspace_id, form_id, statuses=None) -> int:
        where = [
            RegistrationDeliveryRow.workspace_id == _id(workspace_id),
            RegistrationDeliveryRow.form_id == _id(form_id),
        ]
        if statuses:
            where.append(RegistrationDeliveryRow.status.in_(list(statuses)))
        return await self.count(*where)

    async def list_pending_before(
        self, created_before: dt.datetime, limit: int
    ) -> List[RegistrationDeliveryDocument]:
        return await self.many(
            RegistrationDeliveryRow.status == DeliveryStatus.PENDING.value,
            RegistrationDeliveryRow.created_at < created_before,
            order_by=(RegistrationDeliveryRow.created_at, RegistrationDeliveryRow.id),
            limit=limit,
        )

    async def list_stuck_in_progress(
        self, attempted_before: dt.datetime, limit: int
    ) -> List[RegistrationDeliveryDocument]:
        """``in_progress`` with no attempt for a while: the worker died."""
        rows = await self.many(
            RegistrationDeliveryRow.status == DeliveryStatus.IN_PROGRESS.value,
            RegistrationDeliveryRow.updated_at < attempted_before,
            order_by=(RegistrationDeliveryRow.updated_at, RegistrationDeliveryRow.id),
            limit=limit,
        )
        return rows

    async def list_after(
        self, after_id: str, limit: int
    ) -> List[RegistrationDeliveryDocument]:
        return await self.many(
            RegistrationDeliveryRow.id > after_id,
            order_by=(RegistrationDeliveryRow.id,),
            limit=limit,
        )

    async def delete_by_response_id(self, response_id) -> int:
        return await self.delete_where(
            RegistrationDeliveryRow.response_id == _id(response_id)
        )

    async def delete_by_ids(self, ids: Sequence) -> int:
        if not ids:
            return 0
        return await self.delete_where(
            RegistrationDeliveryRow.id.in_([_id(i) for i in ids])
        )

    async def delete_by_registration(self, registration_id) -> int:
        return await self.delete_where(
            RegistrationDeliveryRow.registration_id == _id(registration_id)
        )

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        return await self.delete_where(
            RegistrationDeliveryRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )
