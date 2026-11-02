"""The repository of authenticator-app factors and recovery codes (Postgres
only, new in 4.4).

Every change that must not be half done (confirming a factor, replacing the
recovery codes, accepting a step, burning a code) runs in one transaction
under a row lock, so two requests presenting the same code cannot both win.
"""

import datetime as dt
from typing import List, Optional, Sequence

from common.records.codec import decode, row_values
from common.records.repository import RecordRepository
from common.security.totp import next_last_used_step
from sqlalchemy import select

from backend.app.schemas.user_totp import (
    CONFIRMED,
    PENDING,
    UserRecoveryCodeDocument,
    UserTotpFactorDocument,
)
from backend.db.models import UserRecoveryCodeRow, UserTotpFactorRow


class PostgresUserTotpRepository(RecordRepository):
    row = UserTotpFactorRow
    document = UserTotpFactorDocument

    # -- reads -----------------------------------------------------------------
    async def confirmed(self, user_id: str) -> Optional[UserTotpFactorDocument]:
        return await self.one(
            UserTotpFactorRow.user_id == str(user_id),
            UserTotpFactorRow.state == CONFIRMED,
        )

    async def pending(self, user_id: str) -> Optional[UserTotpFactorDocument]:
        return await self.one(
            UserTotpFactorRow.user_id == str(user_id),
            UserTotpFactorRow.state == PENDING,
        )

    async def codes_left(self, user_id: str) -> int:
        """Unused recovery codes of the account."""
        codes = await self.many(
            UserRecoveryCodeRow.user_id == str(user_id),
            row=UserRecoveryCodeRow,
            document=UserRecoveryCodeDocument,
        )
        return sum(1 for code in codes if code.used_at is None)

    async def users_with_factor(self, user_ids: Sequence[str]) -> set:
        """Which of ``user_ids`` have a confirmed factor (for a member list)."""
        if not user_ids:
            return set()
        async with self._session() as session:
            rows = await session.execute(
                select(UserTotpFactorRow.user_id).where(
                    UserTotpFactorRow.user_id.in_([str(u) for u in user_ids]),
                    UserTotpFactorRow.state == CONFIRMED,
                )
            )
        return set(rows.scalars().all())

    # -- enrolment -------------------------------------------------------------
    async def replace_pending(self, factor: UserTotpFactorDocument) -> None:
        """Store ``factor`` as the account's one pending factor, dropping any
        earlier pending one, in one transaction."""
        async with self._session() as session, session.begin():
            await self._delete_recorded(
                session,
                UserTotpFactorRow,
                UserTotpFactorRow.user_id == factor.user_id,
                UserTotpFactorRow.state == PENDING,
            )
            await session.execute(self._upsert_statement(row_values(factor)))

    async def confirm(
        self,
        user_id: str,
        factor_id: str,
        step: int,
        code_hashes: Sequence[str],
        now: dt.datetime,
        enrolled_via: Optional[str] = None,
    ) -> bool:
        """The whole of a successful confirmation, or nothing: the pending
        factor becomes the confirmed one (``step`` is the code just used), any
        older confirmed factor and its codes are deleted, and the new recovery
        codes are stored. False when the pending factor is gone (replaced,
        purged or already confirmed)."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(UserTotpFactorRow.doc)
                    .where(
                        UserTotpFactorRow.id == str(factor_id),
                        UserTotpFactorRow.user_id == str(user_id),
                        UserTotpFactorRow.state == PENDING,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return False
            factor = decode(UserTotpFactorDocument, doc)
            await self._delete_recorded(
                session,
                UserRecoveryCodeRow,
                UserRecoveryCodeRow.user_id == str(user_id),
            )
            await self._delete_recorded(
                session,
                UserTotpFactorRow,
                UserTotpFactorRow.user_id == str(user_id),
                UserTotpFactorRow.state == CONFIRMED,
            )
            factor.state = CONFIRMED
            factor.confirmed_at = now
            factor.last_used_step = step
            factor.enrolled_via = enrolled_via
            factor.updated_at = now
            await session.execute(self._upsert_statement(row_values(factor)))
            for code_hash in code_hashes:
                await session.execute(
                    self._upsert_statement(
                        row_values(
                            UserRecoveryCodeDocument(
                                factor_id=str(factor.id),
                                user_id=str(user_id),
                                code_hash=code_hash,
                            )
                        ),
                        UserRecoveryCodeRow,
                    )
                )
        return True

    # -- using a factor --------------------------------------------------------
    async def accept_step(self, factor_id: str, matched_step: int) -> bool:
        """Advance ``last_used_step`` to ``matched_step`` if (and only if) it is
        newer: True for exactly one of any number of concurrent submissions of
        the same code."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(UserTotpFactorRow.doc)
                    .where(
                        UserTotpFactorRow.id == str(factor_id),
                        UserTotpFactorRow.state == CONFIRMED,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return False
            factor = decode(UserTotpFactorDocument, doc)
            accepted = next_last_used_step(factor.last_used_step, matched_step)
            if accepted is None:
                return False
            factor.last_used_step = accepted
            await session.execute(self._upsert_statement(row_values(factor)))
        return True

    async def burn_code(self, user_id: str, code_hash: str, now: dt.datetime) -> bool:
        """Mark the account's recovery code burned: True for exactly one of any
        number of concurrent uses of the same code."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(UserRecoveryCodeRow.doc)
                    .where(
                        UserRecoveryCodeRow.user_id == str(user_id),
                        UserRecoveryCodeRow.code_hash == code_hash,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return False
            code = decode(UserRecoveryCodeDocument, doc)
            if code.used_at is not None:
                return False
            code.used_at = now
            code.updated_at = now
            await session.execute(
                self._upsert_statement(row_values(code), UserRecoveryCodeRow)
            )
        return True

    async def lock(
        self, factor_id: str, durations: Sequence[dt.timedelta], now: dt.datetime
    ) -> Optional[dt.timedelta]:
        """Lock the second-factor step for the next of ``durations`` (the first
        lock since an accepted code gets the first, each further one the next,
        the last again after that): the duration when this call started the lock
        (none was running), so the one that did mails and audits it; None
        otherwise."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(UserTotpFactorRow.doc)
                    .where(
                        UserTotpFactorRow.id == str(factor_id),
                        UserTotpFactorRow.state == CONFIRMED,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            factor = decode(UserTotpFactorDocument, doc)
            if factor.locked_until is not None and factor.locked_until > now:
                return None
            duration = durations[min(factor.lock_count, len(durations) - 1)]
            factor.locked_until = now + duration
            factor.lock_count += 1
            await session.execute(self._upsert_statement(row_values(factor)))
        return duration

    async def clear_locks(self, factor_id: str) -> None:
        """A code was accepted: the next lock starts from the shortest again."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(UserTotpFactorRow.doc)
                    .where(UserTotpFactorRow.id == str(factor_id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return
            factor = decode(UserTotpFactorDocument, doc)
            if factor.lock_count:
                factor.lock_count = 0
                await session.execute(self._upsert_statement(row_values(factor)))

    async def replace_codes(
        self, user_id: str, factor_id: str, code_hashes: Sequence[str]
    ) -> bool:
        """Swap the factor's recovery codes for new ones in one transaction;
        False when the account has no such confirmed factor."""
        async with self._session() as session, session.begin():
            found = (
                await session.execute(
                    select(UserTotpFactorRow.id)
                    .where(
                        UserTotpFactorRow.id == str(factor_id),
                        UserTotpFactorRow.user_id == str(user_id),
                        UserTotpFactorRow.state == CONFIRMED,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if found is None:
                return False
            await self._delete_recorded(
                session,
                UserRecoveryCodeRow,
                UserRecoveryCodeRow.user_id == str(user_id),
            )
            for code_hash in code_hashes:
                await session.execute(
                    self._upsert_statement(
                        row_values(
                            UserRecoveryCodeDocument(
                                factor_id=str(factor_id),
                                user_id=str(user_id),
                                code_hash=code_hash,
                            )
                        ),
                        UserRecoveryCodeRow,
                    )
                )
        return True

    # -- removal ---------------------------------------------------------------
    async def delete_for_user(self, user_id: str) -> int:
        """Every factor (pending and confirmed) and recovery code of the
        account; the factors deleted."""
        async with self._session() as session, session.begin():
            await self._delete_recorded(
                session,
                UserRecoveryCodeRow,
                UserRecoveryCodeRow.user_id == str(user_id),
            )
            return await self._delete_recorded(
                session, UserTotpFactorRow, UserTotpFactorRow.user_id == str(user_id)
            )

    async def purge_pending(self, cutoff: dt.datetime) -> int:
        """Pending factors set up before ``cutoff`` (never confirmed)."""
        return await self.delete_where(
            UserTotpFactorRow.state == PENDING, UserTotpFactorRow.created_at < cutoff
        )
