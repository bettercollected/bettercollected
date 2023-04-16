import enum


class WorkspaceRoles(str, enum.Enum):
    ADMIN = "ADMIN"
    COLLABORATOR = "COLLABORATOR"
