import datetime as dt
from typing import Annotated, Any, Dict, List, Optional

from beanie import Indexed, PydanticObjectId
from common.configs.mongo_document import MongoDocument

from backend.app.handlers.database import entity


@entity
class WorkspaceAIProfileDocument(MongoDocument):
    """The workspace's AI profile — the org context every AI call is grounded
    in (see plans/ai-native-form-builder.md §2.3).

    Three plain-markdown sections, deliberately a visible document the
    workspace owns rather than hidden embeddings:
    - ``about``      — tone of voice, audience, languages, vocabulary
    - ``guidelines`` — dos/don'ts for forms
    - ``compliance`` — hard requirements (injected with elevated wording;
                       the AI must not violate these even if asked)

    ``revisions`` keeps the last few versions — it's a policy document, so
    auditability matters more than storage.
    """

    workspace_id: Annotated[PydanticObjectId, Indexed(unique=True)]
    about: str = ""
    guidelines: str = ""
    compliance: str = ""
    updated_by: Optional[str] = None
    revisions: List[Dict[str, Any]] = []

    class Settings:
        name = "workspace_ai_profiles"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
        }
