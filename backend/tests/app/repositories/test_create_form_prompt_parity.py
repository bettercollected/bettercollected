"""The Postgres twin of the AI form-prompt repository behaves like the Mongo
original. Skipped unless DATABASE_URL points at a *_test database."""

from beanie import PydanticObjectId

from backend.app.repositories.create_form_prompt_repository import (
    CreateFormPromptRepository,
)
from backend.app.repositories.postgres.ai import PostgresCreateFormPromptRepository
from backend.app.schemas.create_form_prompts import CreateFormPrompt
from tests.app.repositories.parity import parity, sessions  # noqa: F401


async def test_create_form_prompts(sessions):
    form_id, other = PydanticObjectId(), PydanticObjectId()

    def prompt(text):
        return CreateFormPrompt(
            prompt=text,
            openai_response={"title": "Outline", "sections": [{"title": "One"}]},
            created_form={"title": "Form", "fields": []},
            form_id=form_id,
        )

    await parity(
        CreateFormPromptRepository(),
        PostgresCreateFormPromptRepository(sessions),
        [
            ("list_by_form_id", lambda: (form_id,)),
            ("add", lambda: (prompt("a survey"),)),
            ("add", lambda: (prompt("a survey, again"),)),
            ("list_by_form_id", lambda: (form_id,)),
            ("list_by_form_id", lambda: (str(form_id),)),
            ("list_by_form_id", lambda: (other,)),
        ],
    )
