import { AuditEntryDto, AuditLabels } from '@app/models/dtos/audit-log-dto';

// One plain sentence per audit entry, in the reader's language. The server sends codes, ids and the current labels of
// the ids on the page (never prose, never an answer or an address); the words are here and in
// `public/locales/<lang>/common.json` under `AUDIT_LOG.SENTENCE`. An id never reaches the screen: a person who has left
// is "a member who has left", a form or team that is gone is "an item that no longer exists". An event kind this file
// does not know gets the neutral fallback sentence, so a newer server never breaks the page.

export type Translate = (key: string, options?: Record<string, unknown>) => string;

/** The event kinds the server can return today (backend services/audit_log/catalog.py `AREAS`). */
export const AUDIT_EVENTS = [
    'access_grant_added',
    'access_grant_changed',
    'access_grant_removed',
    'access_mode_changed',
    'team_created',
    'team_renamed',
    'team_deleted',
    'team_member_added',
    'team_member_removed',
    'team_linked',
    'access_member_purged',
    'member_invited',
    'member_invitation_revoked',
    'member_invitation_accepted',
    'member_removed',
    'member_role_changed',
    'form_published',
    'form_deleted',
    'form_creator_reassigned',
    'response_staff_edit',
    'response_revision_read',
    'responses_deleted',
    'response_export',
    'api_key_revoked',
    'api_key_created',
    'api_key_role_changed',
    'api_key_scope_changed',
    'api_key_form_added',
    'api_key_form_removed',
    'sso_break_glass_request',
    'sso_break_glass_sign_in',
    'totp_policy_changed',
    'totp_reset'
] as const;

// Private-use characters that mark the names in a finished sentence, so the page can set them in bold. They are
// stripped from every name first, so a name can never forge a mark.
const OPEN = '\uE000';
const CLOSE = '\uE001';
const SENTENCE = 'AUDIT_LOG.SENTENCE';

export interface SentenceSegment {
    text: string;
    /** A person, form or team named in the sentence. */
    strong: boolean;
}

export interface Sentence {
    /** The plain sentence. */
    text: string;
    segments: SentenceSegment[];
    /** The translation key used: `AUDIT_LOG.SENTENCE.FALLBACK` for an unknown kind. */
    key: string;
}

export interface SentenceContext {
    labels: Partial<AuditLabels> | undefined;
    t: Translate;
    /** The form this list is about: its own sentences say "this form", never its name. */
    formId?: string;
}

const clean = (value: string) => value.replace(/[\uE000\uE001]/g, '');
const mark = (value: string) => `${OPEN}${clean(value)}${CLOSE}`;
const present = (value: string | null | undefined): value is string => typeof value === 'string' && value.length > 0;

/** Split a finished sentence at its marks. */
export function toSegments(marked: string): SentenceSegment[] {
    const segments: SentenceSegment[] = [];
    let strong = false;
    let current = '';
    for (const char of marked) {
        if (char === OPEN || char === CLOSE) {
            if (current) segments.push({ text: current, strong });
            current = '';
            strong = char === OPEN;
        } else {
            current += char;
        }
    }
    if (current) segments.push({ text: current, strong });
    return segments;
}

/** A sentence starts with a capital, whether it begins with a name or with "a member who has left". */
function capitalise(marked: string): string {
    const index = [...marked].findIndex((char) => char !== OPEN && char !== CLOSE);
    if (index < 0) return marked;
    const chars = [...marked];
    chars[index] = chars[index].toLocaleUpperCase();
    return chars.join('');
}

export function describeEntry(entry: AuditEntryDto, { labels, t, formId: fixedForm }: SentenceContext): Sentence {
    const name = (key: string, options?: Record<string, unknown>) => mark(t(`AUDIT_LOG.NAME.${key}`, options));

    const member = (id: string | null | undefined, whenMissing: 'someone' | 'former' = 'someone'): string => {
        if (!present(id)) return name(whenMissing === 'someone' ? 'SOMEONE' : 'FORMER_MEMBER');
        const label = labels?.members?.[id];
        if (label?.status === 'member') return present(label.name) ? mark(label.name) : name('MEMBER_UNNAMED');
        return name('FORMER_MEMBER');
    };
    const form = (id: string | null | undefined): string => {
        if (present(id) && fixedForm && id === fixedForm) return t('AUDIT_LOG.NAME.THIS_FORM');
        const label = present(id) ? labels?.forms?.[id] : undefined;
        if (label?.status === 'available') return present(label.title) ? mark(label.title) : name('UNTITLED_FORM');
        return name('GONE');
    };
    const team = (id: string | null | undefined): string => {
        const label = present(id) ? labels?.teams?.[id] : undefined;
        if (label?.status === 'available' && present(label.name)) return mark(label.name);
        return name('GONE');
    };
    const roleName = (role: string | null | undefined): string => {
        const code = present(role) ? role.toUpperCase() : '';
        // COLLABORATOR is how the server stores an Editor
        const known = code === 'COLLABORATOR' ? 'EDITOR' : code;
        // an API key with no role of its own acts as the member who made it
        if (known === 'CREATOR') return t('AUDIT_LOG.NAME.ROLE_CREATOR');
        return ['OWNER', 'ADMIN', 'EDITOR', 'REVIEWER', 'VIEWER', 'PRIVACY_OFFICER'].includes(known) ? t(`WORKSPACE_ROLES.${known}.NAME`) : t('AUDIT_LOG.NAME.ROLE_UNKNOWN');
    };

    const actor = member(entry.actorId);
    const target = member(entry.targetUserId, 'former');
    const hasCount = typeof entry.count === 'number';
    let key = '';
    let values: Record<string, unknown> = { actor };
    // extra facts appended in brackets (an export's format, a key that gained access)
    const details: string[] = [];

    switch (entry.event) {
        case 'access_grant_added':
        case 'access_grant_changed': {
            const subject = present(entry.targetUserId) ? member(entry.targetUserId) : present(entry.groupId) ? t(`${SENTENCE}.SUBJECT_TEAM`, { team: team(entry.groupId) }) : name('SOMEONE');
            key = entry.event === 'access_grant_added' && entry.grantExport ? 'ACCESS_GRANT_ADDED_EXPORT' : entry.event.toUpperCase();
            values = { actor, subject, role: roleName(entry.grantRole), form: form(entry.formId) };
            break;
        }
        case 'access_grant_removed': {
            const subject = present(entry.targetUserId) ? member(entry.targetUserId) : present(entry.groupId) ? t(`${SENTENCE}.SUBJECT_TEAM`, { team: team(entry.groupId) }) : name('SOMEONE');
            key = 'ACCESS_GRANT_REMOVED';
            values = { actor, subject, form: form(entry.formId) };
            break;
        }
        case 'access_mode_changed':
            key = entry.accessMode === 'restricted' ? 'ACCESS_MODE_CHANGED_RESTRICTED' : entry.accessMode === 'workspace' ? 'ACCESS_MODE_CHANGED_WORKSPACE' : 'ACCESS_MODE_CHANGED_OTHER';
            values = { actor, form: form(entry.formId) };
            break;
        case 'team_created':
        case 'team_renamed':
        case 'team_linked':
            key = entry.event.toUpperCase();
            values = { actor, team: team(entry.groupId) };
            break;
        case 'team_deleted':
            key = hasCount ? 'TEAM_DELETED' : 'TEAM_DELETED_NO_COUNT';
            values = { actor, count: entry.count };
            break;
        case 'team_member_added':
        case 'team_member_removed':
            key = entry.event.toUpperCase();
            values = { actor, target, team: team(entry.groupId) };
            break;
        case 'access_member_purged':
            key = hasCount ? 'ACCESS_MEMBER_PURGED' : 'ACCESS_MEMBER_PURGED_NO_COUNT';
            values = { target, count: entry.count };
            break;
        case 'member_invited':
            key = 'MEMBER_INVITED';
            values = { actor, role: roleName(entry.role) };
            break;
        case 'member_invitation_revoked':
            key = 'MEMBER_INVITATION_REVOKED';
            break;
        case 'member_invitation_accepted':
            key = 'MEMBER_INVITATION_ACCEPTED';
            values = { target: present(entry.targetUserId) ? target : actor, role: roleName(entry.role) };
            break;
        case 'member_removed':
            key = 'MEMBER_REMOVED';
            values = { actor, target };
            break;
        case 'member_role_changed':
            key = present(entry.previousRole) ? 'MEMBER_ROLE_CHANGED' : 'MEMBER_ROLE_CHANGED_NO_PREVIOUS';
            values = { actor, target, role: roleName(entry.role), previous: roleName(entry.previousRole) };
            break;
        case 'form_published':
        case 'form_deleted':
            key = entry.event.toUpperCase();
            values = { actor, form: form(entry.formId) };
            break;
        case 'form_creator_reassigned':
            key = 'FORM_CREATOR_REASSIGNED';
            values = { actor, target, form: form(entry.formId), to: member(entry.toUserId) };
            break;
        case 'response_staff_edit':
        case 'response_revision_read':
            key = typeof entry.revision === 'number' ? entry.event.toUpperCase() : `${entry.event.toUpperCase()}_NO_REVISION`;
            values = { actor, form: form(entry.formId), revision: entry.revision };
            break;
        case 'responses_deleted':
            key = hasCount ? 'RESPONSES_DELETED' : 'RESPONSES_DELETED_NO_COUNT';
            values = { actor, form: form(entry.formId), count: entry.count };
            break;
        case 'response_export': {
            const channel = { response_pdf: 'PDF', all_submissions: 'ALL', api_key: 'API', mcp: 'MCP' }[entry.exportChannel ?? ''];
            key = channel ? `RESPONSE_EXPORT_${channel}` : 'RESPONSE_EXPORT';
            values = { actor, form: form(entry.formId) };
            if (present(entry.exportFormat)) details.push(clean(entry.exportFormat).toUpperCase().slice(0, 12));
            if (hasCount) details.push(t(`${SENTENCE}.DETAIL_ROWS`, { count: entry.count }));
            break;
        }
        case 'api_key_created':
            key = entry.keyRole?.toLowerCase() === 'creator' ? 'API_KEY_CREATED_CREATOR' : present(entry.keyRole) ? 'API_KEY_CREATED_ROLE' : 'API_KEY_CREATED';
            values = { actor, role: roleName(entry.keyRole) };
            if (entry.formScope === 'listed') details.push(t(`${SENTENCE}.DETAIL_KEY_LISTED`));
            break;
        case 'api_key_revoked': {
            const reason = { member_removed: 'MEMBER_REMOVED', account_deleted: 'ACCOUNT_DELETED', scim_deprovisioned: 'DEPROVISIONED' }[entry.reason ?? ''];
            key = reason ? `API_KEY_REVOKED_${reason}` : 'API_KEY_REVOKED';
            values = { actor, target };
            break;
        }
        case 'api_key_role_changed':
            key = present(entry.keyRoleBefore) ? 'API_KEY_ROLE_CHANGED' : 'API_KEY_ROLE_CHANGED_NO_BEFORE';
            values = { actor, role: roleName(entry.keyRole), previous: roleName(entry.keyRoleBefore) };
            if (entry.widened) details.push(t(`${SENTENCE}.DETAIL_KEY_WIDENED`));
            break;
        case 'api_key_scope_changed':
            key = entry.formScope === 'listed' ? 'API_KEY_SCOPE_CHANGED_LISTED' : entry.formScope === 'all' ? 'API_KEY_SCOPE_CHANGED_ALL' : 'API_KEY_SCOPE_CHANGED';
            if (entry.widened) details.push(t(`${SENTENCE}.DETAIL_KEY_WIDENED`));
            break;
        case 'api_key_form_added':
        case 'api_key_form_removed':
            key = entry.event.toUpperCase();
            values = { actor, form: form(entry.formId) };
            if (entry.widened) details.push(t(`${SENTENCE}.DETAIL_KEY_WIDENED`));
            break;
        case 'totp_policy_changed':
            key = entry.required === true ? 'TOTP_POLICY_CHANGED_ON' : entry.required === false ? 'TOTP_POLICY_CHANGED_OFF' : 'TOTP_POLICY_CHANGED';
            break;
        case 'totp_reset':
            key = 'TOTP_RESET';
            values = { actor, target };
            break;
        case 'sso_break_glass_sign_in':
            key = 'SSO_BREAK_GLASS_SIGN_IN';
            break;
        case 'sso_break_glass_request':
            key = 'SSO_BREAK_GLASS_REQUEST';
            break;
        default:
            key = 'FALLBACK';
    }

    let marked = t(`${SENTENCE}.${key}`, values);
    if (details.length > 0) {
        // "... (CSV, 12 responses)." — the facts go before the full stop
        const stem = marked.replace(/\.\s*$/, '');
        marked = `${stem} (${details.join(', ')}).`;
    }
    marked = capitalise(marked);
    const segments = toSegments(marked);
    return { text: segments.map((segment) => segment.text).join(''), segments, key: `${SENTENCE}.${key}` };
}
