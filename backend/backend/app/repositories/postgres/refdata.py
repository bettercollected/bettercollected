"""The refdata group's repositories: Postgres only (its Mongo collections are
read only by the import from 4.0)."""

from typing import List, Optional

from pydantic import BaseModel

from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.models.types.coupon_code import CouponCode
from backend.app.schemas.allowed_origin import AllowedOriginsDocument
from backend.app.schemas.coupon_codes import CouponCodeDocument
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from backend.app.schemas.price_suggestion import PriceSuggestion
from backend.app.schemas.user_feedback import UserFeedbackDocument
from backend.db.models import (
    AllowedOriginRow,
    CouponCodeRow,
    FormPluginConfigRow,
    PriceSuggestionRow,
    UserFeedbackRow,
)
from common.records import RecordId
from common.records.repository import RecordRepository


class PostgresAllowedOriginsRepository(RecordRepository):
    row = AllowedOriginRow
    document = AllowedOriginsDocument

    async def list_origins(self) -> List[str]:
        return [doc.origin for doc in await self.many(order_by=(AllowedOriginRow.id,))]

    async def find_by_origin(self, origin: str) -> Optional[AllowedOriginsDocument]:
        return await self.one(AllowedOriginRow.origin == origin)

    async def add(self, origin: str) -> AllowedOriginsDocument:
        return await self.save_document(AllowedOriginsDocument(origin=origin))

    async def delete_by_origin(self, origin: str) -> None:
        # one row, the oldest, even when an origin is listed twice
        await self.delete_one_where(AllowedOriginRow.origin == origin)


class PostgresFormPluginProviderRepository(RecordRepository):
    row = FormPluginConfigRow
    document = FormPluginConfigDocument

    async def list(self) -> List[FormProviderConfigDto]:
        return [
            FormProviderConfigDto(**provider.model_dump(mode="json"))
            for provider in await self.many()
        ]

    async def get(self, provider_name: str) -> FormPluginConfigDocument | None:
        return await self.one(FormPluginConfigRow.provider_name == provider_name)

    class ProviderUrlProject(BaseModel):
        provider_url: str

    async def get_provider_url(self, provider_name) -> Optional[ProviderUrlProject]:
        document = await self.get(provider_name)
        if document is None:
            return None
        return self.ProviderUrlProject(
            provider_url=document.provider_url
        )

    async def add(self, item: FormPluginConfigDocument) -> FormPluginConfigDocument:
        return await self.save_document(item)

    async def update(
        self, provider_name: str, item: FormPluginConfigDocument
    ) -> FormPluginConfigDocument:
        existing = await self.get(provider_name)
        if existing:
            item.id = existing.id
        return await self.save_document(item)

    async def delete(self, provider_name: str, provider: FormPluginConfigDocument):
        pass  # providers are never deleted


class PostgresCouponRepository(RecordRepository):
    row = CouponCodeRow
    document = CouponCodeDocument

    async def create_coupons(self, coupons: List[CouponCodeDocument]):
        await self.upsert_many(coupons)
        return "Created"

    async def save(self, coupon: CouponCodeDocument) -> CouponCodeDocument:
        return await self.save_document(coupon)

    async def get_all_coupons(self):
        return await self.many()

    async def get_coupon_by_code(self, coupon_code: CouponCode):
        return await self.one(CouponCodeRow.code == str(coupon_code))


class PostgresUserFeedbackRepo(RecordRepository):
    row = UserFeedbackRow
    document = UserFeedbackDocument

    async def save_user_feedback(self, user_feedback: UserFeedbackDocument):
        return await self.save_document(user_feedback)


class PostgresPriceSuggestionRepository(RecordRepository):
    row = PriceSuggestionRow
    document = PriceSuggestion

    async def add(self, suggestion: PriceSuggestion) -> PriceSuggestion:
        return await self.save_document(suggestion)

    async def list_by_user_id(self, user_id: RecordId) -> List[PriceSuggestion]:
        return await self.many(PriceSuggestionRow.user_id == str(user_id))
