/**
 * The state of a form's responses list (page, size, sort, filters), as it is
 * kept in the URL and as the API is asked for it.
 *
 * In the URL: only what is not secret and not a default. The responder-email
 * search is NOT part of it (it is often an email address, and URLs reach
 * logs and analytics): that stays in memory (utils/response-list-memory.ts).
 * Dates are the viewer's own calendar days (`2026-10-31`); the API gets the
 * UTC instants those days begin at in the viewer's time zone.
 *
 * Reading a URL never throws: anything unknown or malformed falls back to the
 * default, so a hand-edited or stale link opens the list, not an error.
 */

export const PAGE_SIZES = [25, 50, 100] as const;
export type PageSize = (typeof PAGE_SIZES)[number];
export const DEFAULT_PAGE_SIZE: PageSize = 25;

export const SORTS = ['newest', 'oldest', 'version-high', 'version-low'] as const;
export type ResponseSort = (typeof SORTS)[number];

export const DELETION_STATUSES = ['none', 'pending', 'declined'] as const;
export type DeletionStatusFilter = (typeof DELETION_STATUSES)[number];

export const RESPONDENTS = ['anonymous', 'known'] as const;
export type RespondentFilter = (typeof RESPONDENTS)[number];

export interface ResponseListState {
    page: number;
    size: PageSize;
    sort: ResponseSort;
    /** First day, inclusive (viewer's calendar). */
    from?: string;
    /** Last day, inclusive (viewer's calendar). */
    to?: string;
    status?: DeletionStatusFilter;
    who?: RespondentFilter;
    version?: number;
    /** Signed handle from the previous page's answer; lets the server seek instead of count. */
    cursor?: string;
}

export const DEFAULT_STATE: ResponseListState = { page: 1, size: DEFAULT_PAGE_SIZE, sort: 'newest' };

/** The parameter names this list owns in a URL. */
export const LIST_PARAMS = ['page', 'size', 'sort', 'from', 'to', 'status', 'who', 'version', 'cursor'] as const;

const MAX_PAGE = 1_000_000;
const MAX_CURSOR_LENGTH = 2048;
const CURSOR = /^[A-Za-z0-9._-]+$/;
const DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

type Source = { get(name: string): string | null };

/** `value` as a calendar day (`YYYY-MM-DD`) that exists, else undefined. */
export function validDay(value: string | null | undefined): string | undefined {
    const match = DAY.exec(value ?? '');
    if (!match) return undefined;
    const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
    const date = new Date(year, month - 1, day);
    const real = date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
    return real && year >= 1970 && year <= 2200 ? value! : undefined;
}

function oneOf<T extends string>(allowed: readonly T[], value: string | null): T | undefined {
    return allowed.find((candidate) => candidate === value);
}

function positiveInt(value: string | null, max: number): number | undefined {
    if (!value || !/^\d{1,9}$/.test(value)) return undefined;
    const number = Number(value);
    return number >= 1 && number <= max ? number : undefined;
}

export function parseResponseListState(params: Source): ResponseListState {
    const size = positiveInt(params.get('size'), 100);
    const from = validDay(params.get('from'));
    let to = validDay(params.get('to'));
    if (from && to && to < from) to = undefined;
    const cursor = params.get('cursor');
    const state: ResponseListState = {
        page: positiveInt(params.get('page'), MAX_PAGE) ?? 1,
        size: (PAGE_SIZES as readonly number[]).includes(size ?? 0) ? (size as PageSize) : DEFAULT_PAGE_SIZE,
        sort: oneOf(SORTS, params.get('sort')) ?? 'newest'
    };
    if (from) state.from = from;
    if (to) state.to = to;
    const status = oneOf(DELETION_STATUSES, params.get('status'));
    if (status) state.status = status;
    const who = oneOf(RESPONDENTS, params.get('who'));
    if (who) state.who = who;
    const version = positiveInt(params.get('version'), 1_000_000);
    if (version) state.version = version;
    if (cursor && cursor.length <= MAX_CURSOR_LENGTH && CURSOR.test(cursor)) state.cursor = cursor;
    return state;
}

/** The URL parameters of a state: defaults are left out. */
export function responseListSearchParams(state: ResponseListState): URLSearchParams {
    const params = new URLSearchParams();
    if (state.page > 1) params.set('page', String(state.page));
    if (state.size !== DEFAULT_PAGE_SIZE) params.set('size', String(state.size));
    if (state.sort !== 'newest') params.set('sort', state.sort);
    if (state.from) params.set('from', state.from);
    if (state.to) params.set('to', state.to);
    if (state.status) params.set('status', state.status);
    if (state.who) params.set('who', state.who);
    if (state.version) params.set('version', String(state.version));
    if (state.cursor) params.set('cursor', state.cursor);
    return params;
}

/** Whether a URL carries any parameter of this list. */
export function hasListParams(params: { has(name: string): boolean }): boolean {
    return LIST_PARAMS.some((name) => params.has(name));
}

/** What narrows the list (not page, size or sort). */
export function activeFilterCount(state: ResponseListState): number {
    return [state.from, state.to, state.status, state.who, state.version].filter((value) => value !== undefined).length;
}

/**
 * Names the list the state describes, without page and cursor: a response's
 * previous/next links are only valid inside the same list.
 */
export function responseListView(state: ResponseListState): string {
    return responseListSearchParams({ ...state, page: 1, cursor: undefined }).toString();
}

/** The UTC instant the viewer's calendar day `day` begins at. */
export function localDayStart(day: string, addDays = 0): string {
    const [year, month, date] = day.split('-').map(Number);
    return new Date(year, month - 1, date + addDays, 0, 0, 0, 0).toISOString();
}

const SORT_PARAMS: Record<ResponseSort, { sort_by: 'created_at' | 'form_version'; sort_order: 'ASCENDING' | 'DESCENDING' }> = {
    newest: { sort_by: 'created_at', sort_order: 'DESCENDING' },
    oldest: { sort_by: 'created_at', sort_order: 'ASCENDING' },
    'version-high': { sort_by: 'form_version', sort_order: 'DESCENDING' },
    'version-low': { sort_by: 'form_version', sort_order: 'ASCENDING' }
};

/** The query parameters the API takes for a state (see the responses list endpoint). */
export function responseListApiParams(state: ResponseListState) {
    return {
        paging: 'keyset' as const,
        page: state.page,
        size: state.size,
        ...SORT_PARAMS[state.sort],
        // the first day's start, and the start of the day after the last: [from, to)
        submittedFrom: state.from ? localDayStart(state.from) : undefined,
        submittedTo: state.to ? localDayStart(state.to, 1) : undefined,
        status: state.status,
        respondent: state.who,
        formVersion: state.version,
        cursor: state.cursor
    };
}

/**
 * The pager's pages: which page numbers to offer around the current one.
 * `known` is the last page that surely exists (exact total, or the lower
 * bound of a capped one, one further while the answer says another follows).
 */
export function nearbyPages(page: number, known: number, radius = 2): number[] {
    const pages: number[] = [];
    for (let candidate = Math.max(1, page - radius); candidate <= Math.min(known, page + radius); candidate++) pages.push(candidate);
    return pages;
}
