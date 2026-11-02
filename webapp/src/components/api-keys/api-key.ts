import { KEY_ROLE_OPTIONS, KeyFormScope, KeyRole, StoredRole, UNKNOWN_ROLE } from './key-rules';

/** An API key as the server lists it (backend `APIKeyDto`). */
export interface APIKey {
    id: string;
    name: string;
    prefix: string;
    scopes: string[];
    revoked: boolean;
    lastUsedAt?: string | null;
    responsesReadAcknowledgedAt?: string | null;
    // the forms a submissions:write key is limited to (none: every form)
    submissionFormIds?: string[] | null;
    // API_KEY_ROLES_ENABLED: the most the key may do (none: as its creator), the forms it may open, and which
    // ones when it has a list. Shown as stored, whatever the switch says.
    role?: string | null;
    formScope?: string;
    forms?: Array<{ id: string; title?: string | null }>;
}

/** The role a key stores, when it is one the screens know (anything else reads as no role). */
export const keyRoleOf = (key: Pick<APIKey, 'role'>): KeyRole | null => (KEY_ROLE_OPTIONS.includes(key.role as KeyRole) ? (key.role as KeyRole) : null);

/** Anything but "all" is a list, as the server reads it. */
export const keyFormScopeOf = (key: Pick<APIKey, 'formScope'>): KeyFormScope => (!key.formScope || key.formScope === 'all' ? 'all' : 'listed');

/** What the key stores as its role: one of ours, none (as its creator), or a value these screens do not know. */
export const keyStoredRoleOf = (key: Pick<APIKey, 'role'>): StoredRole => (key.role == null ? null : keyRoleOf(key) ?? UNKNOWN_ROLE);
