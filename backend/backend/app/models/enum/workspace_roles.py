import enum


class WorkspaceRoles(str, enum.Enum):
    ADMIN: str = "ADMIN"
    COLLABORATOR: str = "COLLABORATOR"
