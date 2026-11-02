import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import type { GrantRole } from '@app/store/workspaces/form-access-api';

/**
 * Helpers for form-level access (teams, grants, restricted forms). Nothing here decides anything: the server checks
 * every rule again on each request. These only keep the screen from offering what it would refuse, and turn its
 * refusals into a sentence.
 */

/** The refusal codes the server sends (`{code, message}` in the body) and the strings that explain them (`STAFF.FORM_ACCESS.ERROR.*`). */
export const FORM_ACCESS_ERROR_CODES = [
    'form_access_off',
    'access_manage_forbidden',
    'grant_above_own_role',
    'export_grant_reserved',
    'cannot_grant_self',
    'privacy_officer_cannot_be_granted',
    'team_name_taken',
    'too_many_teams',
    'team_full',
    'invalid_name',
    'invalid_description',
    'audit_unavailable'
] as const;

/** The translation key of what the server answered to a change: its code when known, else the status, else a plain failure. */
export function formAccessErrorKey(error: unknown): string {
    const status = (error as { status?: number })?.status;
    const code = (error as { data?: { code?: string } })?.data?.code;
    if (code && (FORM_ACCESS_ERROR_CODES as readonly string[]).includes(code)) return `STAFF.FORM_ACCESS.ERROR.${code}`;
    if (status === 404) return 'STAFF.FORM_ACCESS.ERROR.not_found';
    if (status === 403) return 'STAFF.FORM_ACCESS.ERROR.forbidden';
    return 'STAFF.FORM_ACCESS.ERROR.generic';
}

/** What a grant of each role gives (backend services/form_access/model.py GRANT_PERMISSIONS; a grant never deletes the form). */
const GRANT_GIVES: Record<GrantRole, string[]> = {
    EDITOR: [WorkspacePermission.FORM_READ, WorkspacePermission.FORM_EDIT, WorkspacePermission.FORM_SHARE, WorkspacePermission.RESPONSE_READ, WorkspacePermission.RESPONSE_ANNOTATE, WorkspacePermission.RESPONSE_EXPORT, WorkspacePermission.RESPONSE_DELETE, WorkspacePermission.RESPONSE_EDIT, WorkspacePermission.ANALYTICS_READ],
    REVIEWER: [WorkspacePermission.FORM_READ, WorkspacePermission.RESPONSE_READ, WorkspacePermission.RESPONSE_ANNOTATE, WorkspacePermission.ANALYTICS_READ],
    VIEWER: [WorkspacePermission.FORM_READ, WorkspacePermission.RESPONSE_READ, WorkspacePermission.ANALYTICS_READ]
};

export const GRANT_ROLES: GrantRole[] = ['EDITOR', 'REVIEWER', 'VIEWER'];

/**
 * The roles a person may give on this form: those whose rights are all among their own on it (`myPermissions` of the
 * form's access answer). A hint for the picker; the server refuses a role above the giver's own (`grant_above_own_role`).
 */
export function grantableRoles(myPermissions: readonly string[] | undefined): GrantRole[] {
    const held = new Set(myPermissions ?? []);
    return GRANT_ROLES.filter((role) => GRANT_GIVES[role].every((permission) => held.has(permission)));
}

/** An Editor grant exports on its own; the flag only means something for the other two roles. */
export const exportFlagApplies = (role: GrantRole) => role !== 'EDITOR';
