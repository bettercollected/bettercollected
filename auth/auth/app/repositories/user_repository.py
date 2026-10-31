"""The account repository: ``auth.users`` in Postgres, the only store since 4.1
(the 4.0 Mongo collection is read only by ``python -m auth.migrate``)."""

import datetime
from typing import Callable, Dict, List, Optional

from pydantic import EmailStr
from sqlalchemy import and_, func, select

from auth.app.repositories.metric_periods import object_id_at, utc
from auth.app.schemas.user import UserDocument
from auth.db.base import SCHEMA
from auth.db.models import UserRow
from common.ids import RecordId
from common.records.codec import decode, row_values
from common.records.repository import RecordRepository
from common.enums.plan import Plans
from common.enums.roles import Roles
from common.clock import utcnow


def clear_otp(user: UserDocument) -> None:
    """Drop the account's pending sign-in code (unused)."""
    user.otp_code = user.otp_expiry = user.otp_code_for = None


def consume_otp(user: UserDocument) -> None:
    """A sign-in code was used: the roles it was asked for are added (once
    each) and the code is cleared."""
    wanted = [Roles.FORM_RESPONDER]
    if user.otp_code_for == Roles.FORM_CREATOR:
        wanted.append(Roles.FORM_CREATOR)
    for role in wanted:
        if role not in (user.roles or []):
            user.roles = [*(user.roles or []), role]
    clear_otp(user)


class UserRepository(RecordRepository):
    row = UserRow
    document = UserDocument

    async def get_user_by_id(self, user_id: RecordId):
        return await self.get_or_raise(user_id)

    async def get_user_by_email(self, email: str) -> Optional[UserDocument]:
        """The account for ``email``, ignoring case: addresses differing only
        in case are one account (``uq_users_email_lower``, revision 0005)."""
        if not email:
            return None
        return await self.one(func.lower(UserRow.email) == func.lower(email))

    async def get_user_by_stripe_payment_id(
        self, stripe_payment_id: str
    ) -> UserDocument:
        return await self.one(UserRow.stripe_payment_id == stripe_payment_id)

    async def get_user_by_stripe_customer_id(
        self, stripe_customer_id: str
    ) -> UserDocument:
        return await self.one(UserRow.stripe_customer_id == stripe_customer_id)

    async def get_users_by_emails(self, emails: List[EmailStr]):
        """The accounts for ``emails``, ignoring case (as ``get_user_by_email``)."""
        wanted = [func.lower(e) for e in emails or [] if e]
        if not wanted:
            return []
        return await self.many(func.lower(UserRow.email).in_(wanted))

    async def get_users_by_ids(self, user_ids: List[RecordId]):
        return await self.many(UserRow.id.in_([str(i) for i in user_ids]))

    # -- writes ------------------------------------------------------------------
    # Every write of an account re-reads it with its row locked (FOR UPDATE)
    # and changes only its own fields in the same transaction, so a write never
    # stores an older copy of the rest of the document: in particular never an
    # older sign-in code (a used one, or one with fewer wrong tries counted).
    # Only set_user_otp, save_otp_user and change_otp_locked change otp_*.
    async def _change_locked(
        self,
        where,
        change: Callable[[UserDocument], Optional[bool]],
        *,
        touch: bool,
    ) -> Optional[UserDocument]:
        """The first account matching ``where``, loaded with its row locked;
        ``change`` edits it (returning ``False`` to store nothing) and it is
        stored in the same transaction, ``updated_at`` moved when ``touch``.
        ``None`` when nothing matches."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(UserRow.doc)
                    .where(where)
                    .order_by(UserRow.created_at, UserRow.id)
                    .limit(1)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            user = decode(UserDocument, doc)
            if change(user) is not False:
                if touch:
                    user.touch()
                await session.execute(self._upsert_statement(row_values(user)))
            return user

    async def _change_by_id(
        self, user_id: RecordId, change: Callable[[UserDocument], None]
    ) -> UserDocument:
        """``_change_locked`` on the account ``user_id`` (updated_at moved);
        the record layer's ``NotFoundError`` when there is none."""
        found = await self._change_locked(
            UserRow.id == str(user_id), change, touch=True
        )
        return UserDocument.verify_doc_exists(found, {"id": user_id})

    @staticmethod
    def _by_email(email: str):
        return func.lower(UserRow.email) == func.lower(email)

    async def save_otp_user(
        self,
        email: str,
        otp_code: Optional[str] = None,
        otp_expiry: Optional[int] = None,
        creator: bool = True,
    ) -> UserDocument:
        """The account for ``email``, created when there is none (with the
        code given, for the purpose ``creator`` names). An existing account
        gets the code when one is given; without one, only its purpose is
        raised to creator when asked."""
        purpose = Roles.FORM_CREATOR if creator else Roles.FORM_RESPONDER

        def update(user: UserDocument) -> bool:
            if otp_code is not None:
                user.otp_code, user.otp_expiry = otp_code, otp_expiry
                user.otp_code_for = purpose
                return True
            if creator and Roles.FORM_CREATOR not in (user.otp_code_for or ""):
                user.otp_code_for = Roles.FORM_CREATOR
                return True
            return False

        existing = await self._change_locked(self._by_email(email), update, touch=True)
        if existing is not None:
            return existing
        return await self.save_document(
            UserDocument(
                email=email,
                otp_code=otp_code,
                otp_expiry=otp_expiry,
                otp_code_for=purpose,
            )
        )

    async def save_user(
        self,
        email: str,
        first_name: str = None,
        last_name: str = None,
        otp_code: Optional[str] = None,
        otp_expiry: Optional[int] = None,
        creator: bool = True,
        profile_image: Optional[str] = None,
    ) -> UserDocument:
        """The account for ``email``, created when there is none (``otp_code``
        and ``otp_expiry`` are stored only then); ``creator`` adds that role,
        and the names and picture fill in what the account lacks."""
        roles = [Roles.FORM_RESPONDER]
        if creator:
            roles.append(Roles.FORM_CREATOR)

        def update(user_document: UserDocument) -> None:
            if user_document.roles:
                if creator and Roles.FORM_CREATOR not in user_document.roles:
                    user_document.roles.append(Roles.FORM_CREATOR)
            else:
                user_document.roles = list(roles)
            if not (
                user_document.first_name
                and user_document.last_name
                and user_document.profile_image
            ) and (first_name or last_name or profile_image):
                user_document.first_name = (
                    first_name if first_name else user_document.first_name
                )
                user_document.last_name = (
                    last_name if last_name else user_document.last_name
                )
                user_document.profile_image = (
                    profile_image if profile_image else user_document.profile_image
                )

        existing = await self._change_locked(self._by_email(email), update, touch=True)
        if existing is not None:
            return existing
        created = UserDocument(
            email=email, roles=[], otp_code=otp_code, otp_expiry=otp_expiry
        )
        update(created)
        return await self.save_document(created)

    async def set_user_otp(
        self,
        user_id: RecordId,
        otp_code: str,
        otp_expiry: int,
        otp_code_for: Roles,
    ) -> UserDocument:
        def update(user: UserDocument) -> None:
            user.otp_code, user.otp_expiry = otp_code, otp_expiry
            user.otp_code_for = otp_code_for

        return await self._change_by_id(user_id, update)

    async def update_user_names(
        self,
        user_id: RecordId,
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> UserDocument:
        def update(user: UserDocument) -> None:
            user.first_name, user.last_name = first_name, last_name

        return await self._change_by_id(user_id, update)

    async def set_stripe_payment_id(
        self, user_id: RecordId, stripe_payment_id: str
    ) -> UserDocument:
        def update(user: UserDocument) -> None:
            user.stripe_payment_id = stripe_payment_id

        return await self._change_by_id(user_id, update)

    async def set_user_plan(
        self,
        user_id: RecordId,
        plan: Plans,
        stripe_customer_id: Optional[str] = None,
    ) -> UserDocument:
        """The account's plan; ``stripe_customer_id`` is stored too when given
        (a completed checkout)."""

        def update(user: UserDocument) -> None:
            if stripe_customer_id is not None:
                user.stripe_customer_id = stripe_customer_id
            user.plan = plan

        return await self._change_by_id(user_id, update)

    async def clear_user_otp(self, user: UserDocument):
        """Consume ``user``'s code (``consume_otp``) with the purpose ``user``
        names, updated_at left as it is."""

        def update(stored: UserDocument) -> None:
            stored.otp_code_for = user.otp_code_for
            consume_otp(stored)

        await self._change_locked(UserRow.id == str(user.id), update, touch=False)

    async def change_otp_locked(
        self, email: str, change: Callable[[UserDocument], bool]
    ) -> Optional[UserDocument]:
        """The account for ``email`` (ignoring case) loaded with its row locked
        (``FOR UPDATE``); ``change`` edits it and returns whether to store it,
        in the same transaction (updated_at left as it is). Sign-in attempts on
        one account so run one after another: parallel guesses can't share a
        try. ``None`` when there is no such account."""
        if not email:
            return None
        return await self._change_locked(
            self._by_email(email), lambda user: bool(change(user)), touch=False
        )

    async def delete_user(self, user_id: RecordId):
        return await self.delete_by_id(user_id)

    async def case_duplicate_groups(self) -> List[List[str]]:
        """The ids of the accounts whose emails are equal ignoring case, one
        sorted list per address holding two or more; ids only, never an email.
        ``uq_users_email_lower`` (revision 0005) keeps new ones out, so this is
        empty unless rows came in before that index existed."""
        ids = func.array_agg(UserRow.id)
        async with self._session() as session:
            rows = (
                await session.execute(
                    select(ids)
                    .where(UserRow.email.is_not(None))
                    .group_by(func.lower(UserRow.email))
                    .having(func.count() > 1)
                )
            ).all()
        return sorted(sorted(str(i) for i in row[0]) for row in rows)

    # -- platform metrics (admin dashboard) ------------------------------------
    # Users are dated by id (some documents have no created_at).
    async def count_users(
        self, created_since: Optional[datetime.datetime] = None
    ) -> int:
        if created_since is None:
            return await self.count()
        return await self.count(UserRow.id >= str(object_id_at(created_since)))

    async def count_users_active_since(self, since: datetime.datetime) -> int:
        # last_logged_in has no spine column; read from the document.
        last_logged_in = getattr(func, SCHEMA).bc_ts(UserRow.doc["last_logged_in"])
        return await self.count(last_logged_in >= utc(since))

    async def count_users_by_plan(self) -> Dict[str, int]:
        """plan -> users, for every plan; a user without one is on the default
        FREE plan."""
        plan = func.coalesce(UserRow.plan, Plans.FREE.value)
        counts = [func.count().filter(plan == p.value) for p in Plans]
        async with self._session() as session:
            row = (await session.execute(select(*counts).select_from(UserRow))).one()
        return {p.value: n for p, n in zip(Plans, row)}

    async def count_users_created_per_period(
        self, boundaries: List[datetime.datetime]
    ) -> List[int]:
        bounds = [str(object_id_at(b)) for b in boundaries]
        periods = [
            func.count().filter(and_(UserRow.id >= lower, UserRow.id < upper))
            for lower, upper in zip(bounds[:-1], bounds[1:])
        ]
        if not periods:
            return []
        async with self._session() as session:
            row = (await session.execute(select(*periods).select_from(UserRow))).one()
        return list(row)

    async def update_last_logged_in(self, user_id: RecordId):
        """Stamp ``last_logged_in`` (every ``/auth/status``); ``None`` when the
        account is gone."""

        def update(user: UserDocument) -> None:
            user.last_logged_in = utcnow()

        return await self._change_locked(UserRow.id == str(user_id), update, touch=True)
