from typing import List, Optional

from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.models.types.coupon_code import CouponCode
from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.schemas.allowed_origin import AllowedOriginsDocument
from backend.app.schemas.coupon_codes import CouponCodeDocument
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from backend.app.schemas.user_feedback import UserFeedbackDocument
from backend.db.models import (
    AllowedOriginRow,
    CouponCodeRow,
    FormPluginConfigRow,
    UserFeedbackRow,
)
from common.db import PostgresRepositoryBase


class PostgresAllowedOriginsRepository(PostgresRepositoryBase):
    row = AllowedOriginRow
    document = AllowedOriginsDocument

    async def list_origins(self) -> List[str]:
        return [doc.origin for doc in await self.many()]

    async def find_by_origin(self, origin: str) -> Optional[AllowedOriginsDocument]:
        return await self.one(AllowedOriginRow.origin == origin)

    async def add(self, origin: str) -> AllowedOriginsDocument:
        return await self.upsert(AllowedOriginsDocument(origin=origin))

    async def delete_by_origin(self, origin: str) -> None:
        # Mongo's find_one(...).delete() removes a single document; match it.
        await self.delete_one_where(AllowedOriginRow.origin == origin)


class PostgresFormPluginProviderRepository(PostgresRepositoryBase):
    row = FormPluginConfigRow
    document = FormPluginConfigDocument

    async def list(self) -> List[FormProviderConfigDto]:
        return [
            FormProviderConfigDto(**provider.model_dump(mode="json"))
            for provider in await self.many()
        ]

    async def get(self, provider_name: str) -> FormPluginConfigDocument | None:
        return await self.one(FormPluginConfigRow.provider_name == provider_name)

    async def get_provider_url(
        self, provider_name
    ) -> Optional[FormPluginProviderRepository.ProviderUrlProject]:
        document = await self.get(provider_name)
        if document is None:
            return None
        return FormPluginProviderRepository.ProviderUrlProject(
            provider_url=document.provider_url
        )

    async def add(self, item: FormPluginConfigDocument) -> FormPluginConfigDocument:
        return await self.upsert(item)

    async def update(
        self, provider_name: str, item: FormPluginConfigDocument
    ) -> FormPluginConfigDocument:
        existing = await self.get(provider_name)
        if existing:
            item.id = existing.id
        return await self.upsert(item)

    async def delete(self, provider_name: str, provider: FormPluginConfigDocument):
        pass  # the Mongo implementation is a no-op too


class PostgresCouponRepository(PostgresRepositoryBase):
    row = CouponCodeRow
    document = CouponCodeDocument

    async def create_coupons(self, coupons: List[CouponCodeDocument]):
        await self.upsert_many(coupons)
        return "Created"

    async def save(self, coupon: CouponCodeDocument) -> CouponCodeDocument:
        return await self.upsert(coupon)

    async def get_all_coupons(self):
        return await self.many()

    async def get_coupon_by_code(self, coupon_code: CouponCode):
        return await self.one(CouponCodeRow.code == str(coupon_code))


class PostgresUserFeedbackRepo(PostgresRepositoryBase):
    row = UserFeedbackRow
    document = UserFeedbackDocument

    async def save_user_feedback(self, user_feedback: UserFeedbackDocument):
        return await self.upsert(user_feedback)
