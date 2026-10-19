from typing import List

from beanie import PydanticObjectId

from backend.app.schemas.create_form_prompts import CreateFormPrompt
from common.db.routing import write_op


class CreateFormPromptRepository:
    """The prompts forms were generated from (ai group)."""

    @write_op(replay=True)
    async def add(self, prompt: CreateFormPrompt) -> CreateFormPrompt:
        return await prompt.save()

    async def list_by_form_id(
        self, form_id: PydanticObjectId
    ) -> List[CreateFormPrompt]:
        return await CreateFormPrompt.find(
            {"form_id": PydanticObjectId(form_id)}
        ).to_list()
