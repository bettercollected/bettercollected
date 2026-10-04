import enum


class Permission(str, enum.Enum):
    """What a workspace member may do: the only thing services check.

    The catalogue of docs/enterprise-access-model.md §1. Roles map onto these
    in ``backend.app.services.authorization_service``.
    """

    # workspace
    WORKSPACE_MANAGE = "workspace.manage"
    WORKSPACE_BILLING = "workspace.billing"
    MEMBERS_MANAGE = "members.manage"
    SECURITY_MANAGE = "security.manage"
    AI_MANAGE = "ai.manage"
    AUDIT_READ = "audit.read"
    # forms
    FORM_CREATE = "form.create"
    FORM_READ = "form.read"
    FORM_EDIT = "form.edit"
    FORM_DELETE = "form.delete"
    FORM_SHARE = "form.share"
    # responses
    RESPONSE_READ = "response.read"
    RESPONSE_ANNOTATE = "response.annotate"
    RESPONSE_EXPORT = "response.export"
    RESPONSE_DELETE = "response.delete"
    # privacy and aggregates
    PRIVACY_MANAGE = "privacy.manage"
    ANALYTICS_READ = "analytics.read"
