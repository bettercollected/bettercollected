"""The account repository: ``auth.users`` in Postgres, the only store since 4.1
(the 4.0 Mongo collection is read only by ``python -m auth.migrate``)."""

import datetime
from typing import Dict, List, Optional

from pydantic import EmailStr
from sqlalchemy import and_, func, select

from auth.app.repositories.metric_periods import object_id_at, utc
from auth.app.schemas.user import UserDocument
from auth.db.base import SCHEMA
from auth.db.models import UserRow
from common.ids import RecordId
from common.records.repository import RecordRepository
from common.enums.plan import Plans
from common.enums.roles import Roles
from common.clock import utcnow


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

    async def save_otp_user(
        self,
        email: str,
        otp_code: Optional[str] = None,
        otp_expiry: Optional[int] = None,
        creator: bool = True,
    ) -> UserDocument:
        user_document = await self.get_user_by_email(email)
        if not user_document:
            otp_code_for = Roles.FORM_RESPONDER
            if creator:
                otp_code_for = Roles.FORM_CREATOR
            user_document = await self.save_document(
                UserDocument(
                    email=email,
                    otp_code=otp_code,
                    otp_expiry=otp_expiry,
                    otp_code_for=otp_code_for,
                )
            )
        if creator and Roles.FORM_CREATOR not in user_document.otp_code_for:
            user_document.otp_code_for = Roles.FORM_CREATOR
            await self.save_document(user_document)
        return user_document

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
        user_document = await self.get_user_by_email(email)
        roles = [Roles.FORM_RESPONDER]
        if creator:
            roles.append(Roles.FORM_CREATOR)
        if not user_document:
            user_document = UserDocument(
                email=email, roles=roles, otp_code=otp_code, otp_expiry=otp_expiry
            )
        if user_document.roles:
            if creator and Roles.FORM_CREATOR not in user_document.roles:
                user_document.roles.append(Roles.FORM_CREATOR)
        else:
            user_document.roles = roles
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
        return await self.save_document(user_document)

    async def set_user_otp(
        self,
        user_id: RecordId,
        otp_code: str,
        otp_expiry: int,
        otp_code_for: Roles,
    ) -> UserDocument:
        user_document = await self.get_user_by_id(user_id)
        user_document.otp_code = otp_code
        user_document.otp_expiry = otp_expiry
        user_document.otp_code_for = otp_code_for
        return await self.save_document(user_document)

    async def update_user_names(
        self,
        user_id: RecordId,
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> UserDocument:
        user_document = await self.get_user_by_id(user_id)
        user_document.first_name = first_name
        user_document.last_name = last_name
        return await self.save_document(user_document)

    async def set_stripe_payment_id(
        self, user_id: RecordId, stripe_payment_id: str
    ) -> UserDocument:
        user_document = await self.get_user_by_id(user_id)
        user_document.stripe_payment_id = stripe_payment_id
        return await self.save_document(user_document)

    async def set_user_plan(
        self,
        user_id: RecordId,
        plan: Plans,
        stripe_customer_id: Optional[str] = None,
    ) -> UserDocument:
        """The account's plan; ``stripe_customer_id`` is stored too when given
        (a completed checkout)."""
        user_document = await self.get_user_by_id(user_id)
        if stripe_customer_id is not None:
            user_document.stripe_customer_id = stripe_customer_id
        user_document.plan = plan
        return await self.save_document(user_document)

    async def clear_user_otp(self, user: UserDocument):
        user_roles = [Roles.FORM_RESPONDER]
        if user.otp_code_for == Roles.FORM_CREATOR:
            user_roles.append(Roles.FORM_CREATOR)
        stored = await self.one(UserRow.id == str(user.id))
        if stored is None:
            return
        for role in user_roles:  # added once each, updated_at left as it is
            if role not in (stored.roles or []):
                stored.roles = [*(stored.roles or []), role]
        stored.otp_code = stored.otp_expiry = stored.otp_code_for = None
        await self.upsert(stored)

    async def delete_user(self, user_id: RecordId):
        return await self.delete_by_id(user_id)

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
        user_document = await self.one(UserRow.id == str(user_id))
        user_document.last_logged_in = utcnow()
        return await self.save_document(user_document)
