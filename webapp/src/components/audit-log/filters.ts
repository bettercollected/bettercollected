import { AUDIT_AREAS, AuditArea } from '@app/models/dtos/audit-log-dto';

// The Activity page's filters live in the address (`?area=&who=&about=&form=&from=&to=`), so a Privacy officer can send
// the exact view to an Owner. Nothing here is trusted by the server: it validates every value again. These only keep
// a mistyped address from becoming a request the server would refuse.

export interface AuditFilters {
    /** Chosen areas; none means the default view (everything except break-glass requests). */
    areas: AuditArea[];
    /** A user id: who did it. */
    who?: string;
    /** With `who`: also what was done to that person. */
    about: boolean;
    form?: string;
    /** Calendar days, `YYYY-MM-DD`, in UTC. */
    from?: string;
    to?: string;
}

export const EMPTY_FILTERS: AuditFilters = { areas: [], about: false };

// the shape of an id the server accepts (backend audit_log_router `_ID`)
const ID = /^[A-Za-z0-9_.:-]{1,128}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;

const validDay = (value: string | null | undefined): string | undefined => {
    if (!value || !DAY.test(value)) return undefined;
    return Number.isNaN(Date.parse(`${value}T00:00:00Z`)) ? undefined : value;
};
const validId = (value: string | null | undefined): string | undefined => (value && ID.test(value) ? value : undefined);

/** The filters an address holds; anything that is not a known area, an id or a calendar day is dropped. */
export function parseFilters(params: { getAll: (name: string) => string[]; get: (name: string) => string | null }): AuditFilters {
    const areas = AUDIT_AREAS.filter((area) => params.getAll('area').includes(area));
    const who = validId(params.get('who'));
    return {
        areas,
        who,
        about: !!who && params.get('about') === '1',
        form: validId(params.get('form')),
        from: validDay(params.get('from')),
        to: validDay(params.get('to'))
    };
}

/** The address' query string for the filters (without "?"; empty for none). The inverse of `parseFilters`. */
export function filtersToSearch(filters: AuditFilters): string {
    const search = new URLSearchParams();
    filters.areas.forEach((area) => search.append('area', area));
    if (filters.who) {
        search.set('who', filters.who);
        if (filters.about) search.set('about', '1');
    }
    if (filters.form) search.set('form', filters.form);
    if (filters.from) search.set('from', filters.from);
    if (filters.to) search.set('to', filters.to);
    return search.toString();
}

/** How many filters are set (the count on the phone's "Filters" button). The hidden break-glass default is not one. */
export function activeFilterCount(filters: AuditFilters, withForm: boolean): number {
    return filters.areas.length + (filters.who ? 1 : 0) + (withForm && filters.form ? 1 : 0) + (filters.from ? 1 : 0) + (filters.to ? 1 : 0);
}

// The default view hides the break-glass requests (one entry per request of an owner's email-code session: by far the
// most entries). The other kinds of the Security area stay: the sign-ins, the authenticator rule, its resets.
const DEFAULT_AREAS: AuditArea[] = ['access', 'members', 'forms', 'responses', 'api_keys'];
const DEFAULT_EVENTS = ['sso_break_glass_sign_in', 'totp_policy_changed', 'totp_reset'];

/** Whether the break-glass requests are left out of this view. */
export const hidesBreakGlass = (filters: AuditFilters): boolean => filters.areas.length === 0 || !filters.areas.includes('security');

/**
 * The query string of one page request. `formId` fixes the form (the form's own route, which has no `form_id`
 * filter); `cursor` asks for the next, older page. A range is sent as UTC day boundaries, both ends inclusive.
 */
export function auditQuery(filters: AuditFilters, options: { cursor?: string | null; limit?: number } = {}, form?: string): string {
    const search = new URLSearchParams();
    if (options.limit) search.set('limit', String(options.limit));
    if (options.cursor) search.set('cursor', options.cursor);
    if (filters.areas.length > 0) {
        filters.areas.forEach((area) => search.append('area', area));
    } else {
        DEFAULT_AREAS.forEach((area) => search.append('area', area));
        DEFAULT_EVENTS.forEach((event) => search.append('event', event));
    }
    if (filters.who) search.set(filters.about ? 'involving' : 'actor', filters.who);
    if (form) search.set('form_id', form);
    if (filters.from) search.set('from', `${filters.from}T00:00:00Z`);
    if (filters.to) search.set('to', `${filters.to}T23:59:59.999Z`);
    return search.toString();
}
