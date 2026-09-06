"""Postgres twins of the auth repositories (plans/postgres-consolidation.md §4)."""

import datetime
from typing import List, Optional

from beanie import PydanticObjectId
from pydantic import EmailStr

from auth.app.schemas.provider import Provider
from auth.app.schemas.user import UserDocument
from auth.db.models import ProviderRow, UserRow
from common.db import PostgresRepositoryBase
from common.enums.roles import Roles


class PostgresUserRepository(PostgresRepositoryBase):
    row = UserRow
    document = UserDocument

    async def get_user_by_id(self, user_id: PydanticObjectId):
        return await self.get_or_raise(user_id)

    async def get_user_by_email(self, email: str) -> UserDocument:
        return await self.one(UserRow.email == email)

    async def get_user_by_stripe_payment_id(
        self, stripe_payment_id: str
    ) -> UserDocument:
        return await self.one(UserRow.stripe_payment_id == stripe_payment_id)

    async def get_user_by_stripe_customer_id(
        self, stripe_customer_id: str
    ) -> UserDocument:
        return await self.one(UserRow.stripe_customer_id == stripe_customer_id)

    async def get_users_by_emails(self, emails: List[EmailStr]):
        return await self.many(UserRow.email.in_(list(emails)))

    async def get_users_by_ids(self, user_ids: List[PydanticObjectId]):
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
            user_document = await self.upsert(
                UserDocument(
                    email=email,
                    otp_code=otp_code,
                    otp_expiry=otp_expiry,
                    otp_code_for=otp_code_for,
                )
            )
        if creator and Roles.FORM_CREATOR not in user_document.otp_code_for:
            user_document.otp_code_for = Roles.FORM_CREATOR
            await self.upsert(user_document)
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
        return await self.upsert(user_document)

    async def clear_user_otp(self, user: UserDocument):
        user_roles = [Roles.FORM_RESPONDER]
        if user.otp_code_for == Roles.FORM_CREATOR:
            user_roles.append(Roles.FORM_CREATOR)
        stored = await self.one(UserRow.id == str(user.id))
        if stored is None:  # find_one(...).update() on no match is a no-op
            return
        for role in user_roles:  # $addToSet $each
            if role not in (stored.roles or []):
                stored.roles = [*(stored.roles or []), role]
        stored.otp_code = stored.otp_expiry = stored.otp_code_for = None  # $unset
        await self.upsert(stored)

    async def delete_user(self, user_id: PydanticObjectId):
        return await self.delete_by_id(user_id)

    async def update_last_logged_in(self, user_id: PydanticObjectId):
        user_document = await self.one(UserRow.id == str(user_id))
        user_document.last_logged_in = datetime.datetime.now(datetime.timezone.utc)
        return await self.upsert(user_document)


class PostgresProviderRepository(PostgresRepositoryBase):
    row = ProviderRow
    document = Provider

    async def get_provider(self, provider_name: str) -> Provider:
        return Provider.verify_doc_exists(
            await self.one(ProviderRow.provider_name == provider_name),
            Provider.provider_name == provider_name,
        )
