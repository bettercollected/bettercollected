from typing import Optional, List, Dict

from common.records import Record, RecordId


class WorkspaceTags(Record):
    workspace_id: RecordId
    title: str

    class Settings:
        name = "workspace_tags"


class WorkspaceResponderDocument(Record):
    workspace_id: RecordId
    user_id: Optional[str] = None
    email: str
    tags: Optional[List[RecordId]] = None
    metadata: Optional[Dict[str, str]] = None

    class Settings:
        name = "workspace_responder"
