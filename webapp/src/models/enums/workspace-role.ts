// Workspace roles (docs/enterprise-access-model.md §2). The backend reports a
// member's role as one of these; COLLABORATOR is the legacy spelling of
// EDITOR. Gate controls on permissions (useWorkspacePermissions), not on roles.
export const WorkspaceRole = {
    OWNER: 'OWNER',
    ADMIN: 'ADMIN',
    EDITOR: 'EDITOR',
    REVIEWER: 'REVIEWER',
    VIEWER: 'VIEWER',
    PRIVACY_OFFICER: 'PRIVACY_OFFICER'
} as const;

export type WorkspaceRole = (typeof WorkspaceRole)[keyof typeof WorkspaceRole];

// What can be given to a member, highest first. Ownership is transferred.
export const ASSIGNABLE_ROLES: Array<WorkspaceRole> = [WorkspaceRole.ADMIN, WorkspaceRole.EDITOR, WorkspaceRole.REVIEWER, WorkspaceRole.VIEWER, WorkspaceRole.PRIVACY_OFFICER];

/** The role a member or invitation stands for, or undefined when unknown. */
export function toWorkspaceRole(role?: string | null): WorkspaceRole | undefined {
    if (!role) return undefined;
    const value = role.toUpperCase();
    if (value === 'COLLABORATOR') return WorkspaceRole.EDITOR;
    return (Object.values(WorkspaceRole) as Array<string>).includes(value) ? (value as WorkspaceRole) : undefined;
}

/** A member's role: the backend's `role`, else the first of `roles`. */
export function memberRole(member: { role?: string | null; roles?: Array<string> }): WorkspaceRole | undefined {
    return toWorkspaceRole(member.role) ?? toWorkspaceRole(member.roles?.[0]);
}

export const roleLocale = (role: WorkspaceRole) => ({
    name: `WORKSPACE_ROLES.${role}.NAME`,
    description: `WORKSPACE_ROLES.${role}.DESCRIPTION`
});
