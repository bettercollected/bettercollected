// The backend's permission catalogue (backend/app/models/enum/permission.py,
// docs/enterprise-access-model.md §1). The UI shows and hides controls from
// the caller's effective permissions, never from "is owner".
export const WorkspacePermission = {
    WORKSPACE_MANAGE: 'workspace.manage',
    WORKSPACE_BILLING: 'workspace.billing',
    MEMBERS_MANAGE: 'members.manage',
    SECURITY_MANAGE: 'security.manage',
    AI_MANAGE: 'ai.manage',
    AUDIT_READ: 'audit.read',
    FORM_CREATE: 'form.create',
    FORM_READ: 'form.read',
    FORM_EDIT: 'form.edit',
    FORM_DELETE: 'form.delete',
    FORM_SHARE: 'form.share',
    RESPONSE_READ: 'response.read',
    RESPONSE_ANNOTATE: 'response.annotate',
    RESPONSE_EXPORT: 'response.export',
    RESPONSE_DELETE: 'response.delete',
    PRIVACY_MANAGE: 'privacy.manage',
    ANALYTICS_READ: 'analytics.read'
} as const;

export type WorkspacePermission = (typeof WorkspacePermission)[keyof typeof WorkspacePermission];
