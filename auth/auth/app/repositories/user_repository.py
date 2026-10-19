import datetime
import re
from typing import Dict, Optional, List

from beanie import PydanticObjectId
from common.enums.plan import Plans
from common.enums.roles import Roles
from pydantic import EmailStr

from auth.app.repositories.metric_periods import iso_second, object_id_at
from auth.app.schemas.user import UserDocument
from common.db import write_op
from common.clock import utcnow


class UserRepository:
    async def get_user_by_id(self, user_id: PydanticObjectId):
        return await UserDocument.get(user_id)

    async def get_user_by_email(self, email: str) -> UserDocument:
        return await UserDocument.find_one(UserDocument.email == email)

    async def find_users_by_email_ci(self, email: str) -> List[UserDocument]:
        """Accounts whose email equals ``email`` ignoring case (single
        sign-on's lookup; the other sign-ins still match exactly)."""
        return await UserDocument.find(
            {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}}
        ).to_list()

    async def get_user_by_stripe_payment_id(
        self, stripe_payment_id: str
    ) -> UserDocument:
        return await UserDocument.find_one(
            UserDocument.stripe_payment_id == stripe_payment_id
        )

    async def get_user_by_stripe_customer_id(
        self, stripe_customer_id: str
    ) -> UserDocument:
        return await UserDocument.find_one(
            UserDocument.stripe_customer_id == stripe_customer_id
        )

    async def get_users_by_emails(self, emails: List[EmailStr]):
        return await UserDocument.find({"email": {"$in": emails}}).to_list()

    async def get_users_by_ids(self, user_ids: List[PydanticObjectId]):
        return await UserDocument.find({"_id": {"$in": user_ids}}).to_list()

    @write_op(replay=True)
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
            user_document = UserDocument(
                email=email,
                otp_code=otp_code,
                otp_expiry=otp_expiry,
                otp_code_for=otp_code_for,
            )
            user_document = await user_document.save()
        if creator and Roles.FORM_CREATOR not in user_document.otp_code_for:
            user_document.otp_code_for = Roles.FORM_CREATOR
            await user_document.save()
        return user_document

    @write_op(replay=True)
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
                email=email,
                roles=roles,
                otp_code=otp_code,
                otp_expiry=otp_expiry,
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
        return await user_document.save()

    # -- field updates of an existing account -----------------------------------
    # Each reads the stored account and saves it whole, so the mirror (a
    # replayed write) receives the complete document, not just the change.
    @write_op(replay=True)
    async def set_user_otp(
        self,
        user_id: PydanticObjectId,
        otp_code: str,
        otp_expiry: int,
        otp_code_for: Roles,
    ) -> UserDocument:
        """A new sign-in code for an existing account."""
        user_document = await self.get_user_by_id(user_id)
        user_document.otp_code = otp_code
        user_document.otp_expiry = otp_expiry
        user_document.otp_code_for = otp_code_for
        return await user_document.save()

    @write_op(replay=True)
    async def update_user_names(
        self,
        user_id: PydanticObjectId,
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> UserDocument:
        user_document = await self.get_user_by_id(user_id)
        user_document.first_name = first_name
        user_document.last_name = last_name
        return await user_document.save()

    @write_op(replay=True)
    async def set_stripe_payment_id(
        self, user_id: PydanticObjectId, stripe_payment_id: str
    ) -> UserDocument:
        user_document = await self.get_user_by_id(user_id)
        user_document.stripe_payment_id = stripe_payment_id
        return await user_document.save()

    @write_op(replay=True)
    async def set_user_plan(
        self,
        user_id: PydanticObjectId,
        plan: Plans,
        stripe_customer_id: Optional[str] = None,
    ) -> UserDocument:
        """The account's plan; ``stripe_customer_id`` is stored too when given
        (a completed checkout)."""
        user_document = await self.get_user_by_id(user_id)
        if stripe_customer_id is not None:
            user_document.stripe_customer_id = stripe_customer_id
        user_document.plan = plan
        return await user_document.save()

    @write_op
    async def clear_user_otp(self, user: UserDocument):
        user_roles = [Roles.FORM_RESPONDER]
        if user.otp_code_for == Roles.FORM_CREATOR:
            user_roles.append(Roles.FORM_CREATOR)
        await UserDocument.find_one(UserDocument.id == user.id).update(
            {
                "$addToSet": {"roles": {"$each": user_roles}},
                "$unset": {"otp_code": "", "otp_expiry": "", "otp_code_for": ""},
            }
        )

    @write_op
    async def delete_user(self, user_id: PydanticObjectId):
        return await UserDocument.find({"_id": user_id}).delete()

    # -- platform metrics (admin dashboard) ------------------------------------
    # Users are dated by ObjectId (some documents have no created_at);
    # last_logged_in is an ISO string, compared at second precision.
    async def count_users(
        self, created_since: Optional[datetime.datetime] = None
    ) -> int:
        query = {}
        if created_since is not None:
            query = {"_id": {"$gte": object_id_at(created_since)}}
        return await UserDocument.find(query).count()

    async def count_users_active_since(self, since: datetime.datetime) -> int:
        return await UserDocument.find(
            {"last_logged_in": {"$gte": iso_second(since)}}
        ).count()

    async def count_users_by_plan(self) -> Dict[str, int]:
        """plan -> users, for every plan; a user without one is on the default
        FREE plan."""
        counts = {}
        for plan in Plans:
            values = [plan.value, None] if plan == Plans.FREE else [plan.value]
            counts[plan.value] = await UserDocument.find(
                {"plan": {"$in": values}}
            ).count()
        return counts

    async def count_users_created_per_period(
        self, boundaries: List[datetime.datetime]
    ) -> List[int]:
        """Users created in each period [boundaries[i], boundaries[i+1])."""
        bounds = [object_id_at(b) for b in boundaries]
        return [
            await UserDocument.find({"_id": {"$gte": lower, "$lt": upper}}).count()
            for lower, upper in zip(bounds[:-1], bounds[1:])
        ]

    @write_op
    async def update_last_logged_in(self, user_id: PydanticObjectId):
        user_document = await UserDocument.find_one(UserDocument.id == user_id)
        user_document.last_logged_in = utcnow()
        return await user_document.save()
