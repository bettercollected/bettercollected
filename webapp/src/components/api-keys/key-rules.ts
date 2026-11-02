// What an API key's role and list of forms may be, checked in the browser before anything is sent. This is the
// twin of the server's rules (backend services/api_key_roles: model.py, validation.py), so a combination the
// server refuses is explained here, in plain words, instead of coming back as an error. The server stays
// authoritative: it checks again, and everything here only ever refuses more, never less.
import { WorkspacePermission as P } from '@app/models/enums/workspace-permission';

export type KeyRole = 'EDITOR' | 'REVIEWER' | 'VIEWER' | 'PRIVACY_OFFICER';
export type KeyFormScope = 'all' | 'listed';

// the order a "lowest role that allows these scopes" is looked for in
export const KEY_ROLES: KeyRole[] = ['VIEWER', 'REVIEWER', 'PRIVACY_OFFICER', 'EDITOR'];
// the order the select shows them in (as in the members screens)
export const KEY_ROLE_OPTIONS: KeyRole[] = ['EDITOR', 'REVIEWER', 'VIEWER', 'PRIVACY_OFFICER'];

// at most this many forms on a key's list
export const MAX_KEY_FORMS = 200;

export const SUBMISSIONS_SCOPE = 'submissions:write';

// A scope needs these permissions (backend api_access.SCOPE_PERMISSIONS).
const SCOPE_PERMISSIONS: Record<string, string[]> = {
    'forms:read': [P.FORM_READ],
    'forms:write': [P.FORM_EDIT],
    'forms:delete': [P.FORM_DELETE],
    'responses:read': [P.RESPONSE_READ, P.RESPONSE_EXPORT],
    'deletion_requests:read': [P.PRIVACY_MANAGE],
    'deletion_requests:write': [P.PRIVACY_MANAGE],
    [SUBMISSIONS_SCOPE]: [P.FORM_EDIT]
};

// What a role holds (backend authorization_service.ROLE_PERMISSIONS).
const ROLE_PERMISSIONS: Record<KeyRole, string[]> = {
    EDITOR: [P.FORM_CREATE, P.FORM_READ, P.FORM_EDIT, P.FORM_DELETE, P.FORM_SHARE, P.RESPONSE_READ, P.RESPONSE_ANNOTATE, P.RESPONSE_EXPORT, P.RESPONSE_DELETE, P.RESPONSE_EDIT, P.ANALYTICS_READ],
    REVIEWER: [P.FORM_READ, P.RESPONSE_READ, P.RESPONSE_ANNOTATE, P.ANALYTICS_READ],
    VIEWER: [P.FORM_READ, P.RESPONSE_READ, P.ANALYTICS_READ],
    PRIVACY_OFFICER: [P.FORM_READ, P.PRIVACY_MANAGE, P.ANALYTICS_READ, P.AUDIT_READ]
};

// A key limited to a list of forms never carries these: a grant on a form holds neither form.delete nor
// privacy.manage.
const LISTED_REFUSED_SCOPES = ['forms:delete', 'deletion_requests:read', 'deletion_requests:write'];

/** What a key of `role` may do at most, given its scopes; `null` is no limit (no role: as its creator). */
export function roleCeiling(role: KeyRole | null, scopes: string[]): Set<string> | null {
    if (role === null) return null;
    const held = new Set(ROLE_PERMISSIONS[role] ?? []);
    // a Reviewer or Viewer key exports answers when, and only when, it carries the scope that reads them
    if ((role === 'REVIEWER' || role === 'VIEWER') && scopes.includes('responses:read')) held.add(P.RESPONSE_EXPORT);
    return held;
}

/** Whether a key of this role can carry the scope (no role: always). */
export function roleAllowsScope(role: KeyRole | null, scope: string): boolean {
    const ceiling = roleCeiling(role, [scope]);
    if (ceiling === null) return true;
    const needed = SCOPE_PERMISSIONS[scope];
    return !!needed && needed.every((permission) => ceiling.has(permission));
}

/** Whether a key limited to a list of forms can carry the scope. */
export function listAllowsScope(scope: string): boolean {
    return !LISTED_REFUSED_SCOPES.includes(scope);
}

/** The lowest role that allows every scope, or `null` when none does (then the key follows its creator). */
export function lowestRoleFor(scopes: string[]): KeyRole | null {
    return KEY_ROLES.find((role) => scopes.every((scope) => roleAllowsScope(role, scope))) ?? null;
}

export type ScopeProblem = { scope: string; reason: 'role' | 'list' };

/** Every scope the role or the list cannot carry. Empty means the combination is one the server accepts. */
export function scopeProblems(role: KeyRole | null, formScope: KeyFormScope, scopes: string[]): ScopeProblem[] {
    const problems: ScopeProblem[] = [];
    for (const scope of scopes) {
        if (formScope === 'listed' && !listAllowsScope(scope)) problems.push({ scope, reason: 'list' });
        else if (!roleAllowsScope(role, scope)) problems.push({ scope, reason: 'role' });
    }
    return problems;
}

/** Whether `next` lets the key do something `previous` did not. */
export function widensRole(previous: KeyRole | null, next: KeyRole | null, scopes: string[]): boolean {
    if (next === null) return previous !== null;
    if (previous === null) return false;
    const before = roleCeiling(previous, scopes) as Set<string>;
    return [...(roleCeiling(next, scopes) as Set<string>)].some((permission) => !before.has(permission));
}

export interface KeyLimits {
    role: KeyRole | null;
    formScope: KeyFormScope;
    formIds: string[];
}

/** Whether an edit gives the key more reach: a higher role, a list lifted, more forms on the list. */
export function widensKey(before: KeyLimits, after: KeyLimits, scopes: string[]): boolean {
    if (widensRole(before.role, after.role, scopes)) return true;
    if (before.formScope === 'listed' && after.formScope === 'all') return true;
    if (before.formScope === 'listed' && after.formScope === 'listed') return after.formIds.some((id) => !before.formIds.includes(id));
    return false;
}

/** A form the key submits to that is not on the key's list (the server refuses it; the picker says so first). */
export function submissionFormsOutsideList(submissionFormIds: string[] | null | undefined, formScope: KeyFormScope, formIds: string[]): string[] {
    if (formScope !== 'listed' || !submissionFormIds) return [];
    return submissionFormIds.filter((id) => !formIds.includes(id));
}

/** The server's refusals of a key request, by `code`, each with the text that says what to do. */
export const KEY_ERROR_CODES: Record<string, string> = {
    api_key_roles_off: 'STAFF.API_KEYS.ERR_OFF',
    key_exceeds_editor: 'STAFF.API_KEYS.ERR_EXCEEDS_EDITOR',
    key_role_exceeds_creator: 'STAFF.API_KEYS.ERR_EXCEEDS_CREATOR',
    key_form_scope: 'STAFF.API_KEYS.ERR_FORM_SCOPE',
    key_role_lacks_permission: 'STAFF.API_KEYS.ERR_ROLE_LACKS',
    key_changed: 'STAFF.API_KEYS.ERR_CHANGED',
    key_revoked: 'STAFF.API_KEYS.ERR_REVOKED',
    unknown_key_scope: 'STAFF.API_KEYS.ERR_UNKNOWN_SCOPE',
    scope_not_allowed_by_role: 'STAFF.API_KEYS.ERR_NOT_ALLOWED',
    scope_not_allowed_for_listed_key: 'STAFF.API_KEYS.ERR_NOT_ALLOWED_LISTED',
    invalid_key_role: 'STAFF.API_KEYS.ERR_INVALID_ROLE',
    invalid_form_scope: 'STAFF.API_KEYS.ERR_INVALID_SCOPE',
    form_ids_required: 'STAFF.API_KEYS.ERR_FORMS_REQUIRED',
    form_ids_need_listed_scope: 'STAFF.API_KEYS.ERR_FORMS_NEED_LIST',
    form_not_in_workspace: 'STAFF.API_KEYS.ERR_FORM_UNKNOWN',
    submission_form_outside_list: 'STAFF.API_KEYS.ERR_SUBMISSION_OUTSIDE'
};

/** The `code` of a refused request's body, when it has one. */
export function errorCode(data: unknown): string | undefined {
    const code = (data as { code?: unknown } | null | undefined)?.code;
    return typeof code === 'string' ? code : undefined;
}

/** The scope a refusal names ("... the scope 'forms:delete' ..."), so the message can say it in the user's words. */
export function scopeNamedBy(data: unknown): string | undefined {
    const message = (data as { message?: unknown } | null | undefined)?.message;
    return typeof message === 'string' ? /'([a-z_]+:[a-z_]+)'/.exec(message)?.[1] : undefined;
}
