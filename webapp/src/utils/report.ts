/**
 * Reports on a form's answers (docs/reporting.md): the shapes of the API's
 * catalogue and result, the default Overview a form starts from, the checks a
 * card must pass before it is asked for, and the report's address.
 *
 * What the address carries: the responses list's own filters (`from`, `to`,
 * `status`, `who`, `version`) and, once the viewer changed the cards, the cards
 * (`cards`, base64url of compact JSON: question ids, built-in names, enums;
 * never an answer or a name). Reading an address never throws: anything
 * unknown or malformed falls back to the Overview.
 */

/* ------------------------------------------------------------ the API */

export type ReportFieldKind = 'choice' | 'choices' | 'yes_no' | 'scale' | 'number' | 'currency' | 'calculated' | 'date';
export type ReportAgg = 'count' | 'avg' | 'sum' | 'min' | 'max';
export type ReportCardKind = 'tile' | 'bar' | 'donut' | 'line' | 'table';
export type ReportBucket = 'day' | 'week' | 'month' | 'year';

export const REPORT_AGGS: readonly ReportAgg[] = ['count', 'avg', 'sum', 'min', 'max'];
export const REPORT_KINDS: readonly ReportCardKind[] = ['tile', 'bar', 'donut', 'line', 'table'];
export const REPORT_BUCKETS: readonly ReportBucket[] = ['day', 'week', 'month', 'year'];

/** A donut is parts of a whole: at most this many slices (the server's rule too). */
export const DONUT_MAX = 6;
/** The Overview lists this many questions before "Show all". */
export const OVERVIEW_QUESTIONS = 12;

export interface ReportFieldOption {
    id: string;
    label: string;
}

export interface ReportField {
    key: string;
    label: string;
    kind: ReportFieldKind;
    dimension: boolean;
    measures: ReportAgg[];
    versions?: number[];
    inCurrentVersion?: boolean;
    options?: ReportFieldOption[];
    /** A currency question's one currency (ISO code). */
    currency?: string;
    /** The operators a condition on this question's answer may use. */
    filterOps?: string[];
}

export interface ReportBuiltin {
    key: string;
    buckets?: ReportBucket[];
    measures?: ReportAgg[];
    groups?: Array<{ key: string; label: string }>;
}

export interface ReportCatalogue {
    fields: ReportField[];
    builtins: ReportBuiltin[];
    limits: { maxRows: number; maxCards: number; maxMeasures: number };
}

export interface ReportMeasure {
    agg: ReportAgg;
    field?: string;
}

export interface ReportDimension {
    field: string;
    bucket?: ReportBucket;
}

export interface ReportCardDef {
    id: string;
    kind: ReportCardKind;
    dimension?: ReportDimension;
    measures: ReportMeasure[];
    title?: string;
}

/** A condition on an answer: a question, an operator and a value that is an option id, a number, a yes/no or a date. */
export interface ReportClause {
    field: string;
    op: string;
    value?: boolean | number | string | Array<number | string>;
}

export interface ReportFilters {
    submittedFrom?: string;
    submittedTo?: string;
    status?: string[];
    respondent?: string;
    formVersion?: number[];
    /** Every one of these must be met by a response for it to count. */
    where?: ReportClause[];
}

/** The most conditions on answers a definition holds (the server's limit). */
export const CLAUSES_MAX = 10;

/** A page of the responses behind one group of one card (drill-down). */
export interface ReportDrillRow {
    /** What the response's own page is opened by. */
    id: string;
    submittedAt: string | null;
    formVersion: number | null;
    respondent: 'anonymous' | 'known';
}

export interface ReportDrillPage {
    responses: ReportDrillRow[];
    /** Where to continue; null at the end of the set. */
    cursor: string | null;
    scanned: number;
    /** The set has ended (a short page with a cursor means the scan budget ended, not the set). */
    exhausted: boolean;
}

export interface ReportDefinition {
    v: 1;
    filters: ReportFilters;
    tz: string;
    cards: ReportCardDef[];
}

export interface ReportGroup {
    key: string;
    label: string;
    n: number;
    values: Array<number | null>;
    valueN: number[];
}

export interface ReportCardResult {
    id: string;
    n: number;
    answered: number;
    skipped: number;
    multiple: boolean;
    groups: ReportGroup[];
    otherGroups: { n: number; count: number };
    truncated: boolean;
}

export interface ReportResult {
    definitionHash: string;
    token: string;
    generatedAt: string;
    n: number;
    scanned: number;
    cards: ReportCardResult[];
    notices: string[];
}

/* ------------------------------------------------------- saved views */

export type ReportViewScope = 'private' | 'form';

/** A saved view as the API lists it: a name, a scope and the definition it was saved with. */
export interface ReportView {
    id: string;
    name: string;
    scope: ReportViewScope;
    /** Made by the signed-in member. */
    mine: boolean;
    /** The maker's name; null when it is mine, or when they are no longer a member. */
    ownerName: string | null;
    revision: number;
    createdAt: string | null;
    updatedAt: string | null;
    definition: ReportDefinition;
    canEdit: boolean;
    canDelete: boolean;
}

export interface ReportViewList {
    views: ReportView[];
    /** The member may save a view for everyone who can open the report (form.edit). */
    canShare: boolean;
    limits: { nameMax: number; formViews: number; privateViews: number };
}

/** The codes of a refusal the page tells apart (the API's `code`). */
export type ReportErrorCode = 'view_not_found' | 'view_changed' | 'view_name_taken' | 'view_limit' | 'view_forbidden' | 'invalid_view' | 'too_many_rows' | 'rate_limited' | 'report_busy' | 'report_timeout' | 'reporting_off' | 'invalid_definition' | 'unknown_field' | 'field_not_reportable' | 'op_not_allowed';

export interface ReportError {
    status?: number;
    code?: string;
    count?: number;
    max?: number;
    retryAfter?: number;
}

/** What an RTK Query error holds, as the page's error. */
export function reportErrorOf(error: unknown): ReportError {
    const raw = error as { status?: unknown; data?: { code?: unknown; count?: unknown; max?: unknown; detail?: unknown } } | undefined;
    const data = raw?.data && typeof raw.data === 'object' ? raw.data : undefined;
    const detail = data?.detail && typeof data.detail === 'object' ? (data.detail as { code?: unknown; count?: unknown; max?: unknown }) : undefined;
    const source = { ...(detail ?? {}), ...(data ?? {}) } as { code?: unknown; count?: unknown; max?: unknown };
    return {
        status: typeof raw?.status === 'number' ? raw.status : undefined,
        code: typeof source.code === 'string' ? source.code : undefined,
        count: typeof source.count === 'number' ? source.count : undefined,
        max: typeof source.max === 'number' ? source.max : undefined
    };
}

/* ------------------------------------------------ what a field may be */

export function fieldOf(catalogue: ReportCatalogue, key: string | undefined): ReportField | undefined {
    return key ? catalogue.fields.find((field) => field.key === key) : undefined;
}

export function builtinOf(catalogue: ReportCatalogue, key: string | undefined): ReportBuiltin | undefined {
    return key ? catalogue.builtins.find((builtin) => builtin.key === key) : undefined;
}

export const isTimeDimension = (catalogue: ReportCatalogue, key: string | undefined) => key === 'submitted_at' || fieldOf(catalogue, key)?.kind === 'date';

/**
 * How many groups a dimension surely has, or undefined when it is not known up
 * front. A donut needs it (the server refuses one it cannot count): a single
 * choice has its options plus "Other" and "Removed option".
 */
export function fixedGroups(catalogue: ReportCatalogue, key: string | undefined): number | undefined {
    const field = fieldOf(catalogue, key);
    if (field) {
        if (field.kind === 'choice') return (field.options?.length ?? 0) + 2;
        if (field.kind === 'yes_no') return 2;
        return undefined;
    }
    const builtin = builtinOf(catalogue, key);
    if (!builtin || key === 'form_version' || key === 'submitted_at' || key === 'feedback_status') return undefined;
    if (key === 'ending') return (builtin.groups?.length ?? 0) + 1;
    return builtin.groups?.length;
}

export const canDonut = (catalogue: ReportCatalogue, key: string | undefined) => {
    const groups = fixedGroups(catalogue, key);
    return groups !== undefined && groups <= DONUT_MAX;
};

/** The kinds a card with this dimension may take. */
export function kindsFor(catalogue: ReportCatalogue, dimension: string | undefined): ReportCardKind[] {
    if (!dimension) return ['tile', 'table'];
    if (isTimeDimension(catalogue, dimension)) return ['line', 'bar', 'table'];
    return canDonut(catalogue, dimension) ? ['bar', 'donut', 'table'] : ['bar', 'table'];
}

/** The aggregates a card may show: what its measure question allows; a count for any other. */
export function aggsFor(field: ReportField | undefined): ReportAgg[] {
    return field ? field.measures : ['count'];
}

/** Fields a value (average, sum, min, max) may be taken of. */
export function numericFields(catalogue: ReportCatalogue, agg: ReportAgg): ReportField[] {
    return catalogue.fields.filter((field) => field.measures.includes(agg));
}

/** Fields and built-ins a card may be grouped by. */
export function dimensionKeys(catalogue: ReportCatalogue): string[] {
    return [...catalogue.fields.filter((field) => field.dimension).map((field) => field.key), ...catalogue.builtins.map((builtin) => builtin.key)];
}

export function bucketsOf(catalogue: ReportCatalogue, key: string | undefined): ReportBucket[] {
    if (!isTimeDimension(catalogue, key)) return [];
    return builtinOf(catalogue, key)?.buckets ?? [...REPORT_BUCKETS];
}

/** Why a card cannot be asked for as it is, or undefined when it can. `unknown` names a question the form no longer has. */
export function cardProblem(card: ReportCardDef, catalogue: ReportCatalogue): 'unknown' | 'invalid' | undefined {
    const known = (key: string | undefined) => !!key && (!!fieldOf(catalogue, key) || !!builtinOf(catalogue, key));
    if (card.dimension && !known(card.dimension.field)) return 'unknown';
    if (card.measures.some((measure) => measure.field && !fieldOf(catalogue, measure.field))) return 'unknown';
    if (!REPORT_KINDS.includes(card.kind) || card.measures.length < 1) return 'invalid';
    if (!kindsFor(catalogue, card.dimension?.field).includes(card.kind)) return 'invalid';
    const dimensionField = fieldOf(catalogue, card.dimension?.field);
    if (card.dimension && dimensionField && !dimensionField.dimension) return 'invalid';
    for (const measure of card.measures) {
        if (measure.agg === 'count') {
            if (measure.field) return 'invalid';
            continue;
        }
        const field = fieldOf(catalogue, measure.field);
        if (!field || !field.measures.includes(measure.agg)) return 'invalid';
    }
    return undefined;
}

/* ------------------------------------------------------ the Overview */

let counter = 0;
export const newCardId = () => `c${Date.now().toString(36)}${(counter++).toString(36)}`;

/**
 * The report a form starts from, computed from its catalogue and never stored:
 * the response count, responses over time, then one card per reportable question
 * in form order (a rating or number question also gets its average as a tile).
 * `all` lists every question (up to the card limit), else the first
 * `OVERVIEW_QUESTIONS`.
 */
export function overviewCards(catalogue: ReportCatalogue, all = false): ReportCardDef[] {
    const cards: ReportCardDef[] = [
        { id: 'total', kind: 'tile', measures: [{ agg: 'count' }] },
        { id: 'time', kind: 'line', dimension: { field: 'submitted_at', bucket: 'day' }, measures: [{ agg: 'count' }] }
    ];
    const room = Math.max(0, (catalogue.limits?.maxCards ?? 24) - cards.length);
    const fields = catalogue.fields.slice(0, all ? room : Math.min(OVERVIEW_QUESTIONS, room));
    for (const [index, field] of fields.entries()) {
        const id = `q${index + 1}`;
        if (field.kind === 'number' || field.kind === 'currency') {
            cards.push({ id, kind: 'tile', measures: [{ agg: 'avg', field: field.key }] });
        } else if (field.kind === 'scale') {
            cards.push({ id, kind: 'bar', dimension: { field: field.key }, measures: [{ agg: 'count' }] });
        } else if (field.kind === 'date') {
            cards.push({ id, kind: 'line', dimension: { field: field.key, bucket: 'month' }, measures: [{ agg: 'count' }] });
        } else if (field.dimension) {
            cards.push({ id, kind: 'bar', dimension: { field: field.key }, measures: [{ agg: 'count' }] });
        }
    }
    return cards;
}

/* ------------------------------------------------------- the address */

const MAX_CARDS_PARAM = 6000;

export function toBase64Url(text: string): string {
    const bytes = new TextEncoder().encode(text);
    let binary = '';
    bytes.forEach((byte) => (binary += String.fromCharCode(byte)));
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function fromBase64Url(text: string): string {
    const padded = text.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((text.length + 3) % 4);
    const binary = atob(padded);
    return new TextDecoder().decode(Uint8Array.from(binary, (char) => char.charCodeAt(0)));
}

const FIELD_KEY = /^(q:[\w.:-]{1,100}|[a-z_]{1,30})$/;

function cleanCard(raw: unknown): ReportCardDef | undefined {
    if (!raw || typeof raw !== 'object') return undefined;
    const card = raw as Record<string, unknown>;
    if (typeof card.id !== 'string' || !/^[\w-]{1,64}$/.test(card.id)) return undefined;
    if (!REPORT_KINDS.includes(card.kind as ReportCardKind)) return undefined;
    if (!Array.isArray(card.measures) || card.measures.length < 1 || card.measures.length > 5) return undefined;
    const measures: ReportMeasure[] = [];
    for (const measure of card.measures as Array<Record<string, unknown>>) {
        if (!measure || !REPORT_AGGS.includes(measure.agg as ReportAgg)) return undefined;
        if (measure.field !== undefined && (typeof measure.field !== 'string' || !FIELD_KEY.test(measure.field))) return undefined;
        measures.push(measure.field === undefined ? { agg: measure.agg as ReportAgg } : { agg: measure.agg as ReportAgg, field: measure.field as string });
    }
    const result: ReportCardDef = { id: card.id, kind: card.kind as ReportCardKind, measures };
    if (card.dimension !== undefined) {
        const dimension = card.dimension as Record<string, unknown>;
        if (!dimension || typeof dimension.field !== 'string' || !FIELD_KEY.test(dimension.field)) return undefined;
        if (dimension.bucket !== undefined && !REPORT_BUCKETS.includes(dimension.bucket as ReportBucket)) return undefined;
        result.dimension = dimension.bucket === undefined ? { field: dimension.field } : { field: dimension.field, bucket: dimension.bucket as ReportBucket };
    }
    return result;
}

/** The cards an address carries, or undefined when it carries none (the Overview) or they are malformed. */
export function parseCardsParam(value: string | null | undefined): ReportCardDef[] | undefined {
    if (!value || value.length > MAX_CARDS_PARAM) return undefined;
    try {
        const raw = JSON.parse(fromBase64Url(value));
        if (!Array.isArray(raw) || raw.length > 24) return undefined;
        const cards: ReportCardDef[] = [];
        for (const item of raw) {
            const card = cleanCard(item);
            if (!card || cards.some((other) => other.id === card.id)) return undefined;
            cards.push(card);
        }
        return cards;
    } catch {
        return undefined;
    }
}

export function cardsParam(cards: ReportCardDef[]): string {
    return toBase64Url(JSON.stringify(cards.map(({ id, kind, dimension, measures }) => ({ id, kind, ...(dimension ? { dimension } : {}), measures }))));
}

/** The viewer's IANA zone, for day, week and month groups. */
export function viewerZone(): string {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
        return 'UTC';
    }
}

/* ------------------------------------------------------- the filters */

/** The report's filters as the API's names, from the list's filter state (viewer days to UTC instants). */
export function reportFilters(state: { from?: string; to?: string; status?: string; who?: string; version?: number }, dayStart: (day: string, add?: number) => string, where: ReportClause[] = []): ReportFilters {
    const filters: ReportFilters = {};
    if (where.length) filters.where = where;
    if (state.from) filters.submittedFrom = dayStart(state.from);
    if (state.to) filters.submittedTo = dayStart(state.to, 1);
    if (state.status) filters.status = [state.status];
    if (state.who) filters.respondent = state.who;
    if (state.version !== undefined) filters.formVersion = [state.version];
    return filters;
}

export function reportDefinition(cards: ReportCardDef[], filters: ReportFilters, tz: string): ReportDefinition {
    return { v: 1, filters, tz, cards: cards.map(({ id, kind, dimension, measures }) => ({ id, kind, ...(dimension ? { dimension } : {}), measures })) };
}

/* ---------------------------------------------------- group labels */

/** Group keys the server names in English; the page says them in the viewer's language (`REPORT.GROUP.*`). */
export const FIXED_GROUP_KEYS = ['yes', 'no', 'other', 'removed', 'none', 'anonymous', 'known', 'form', 'api', 'csv', 'pending', 'declined', 'success'] as const;

export function isFixedGroupKey(key: string): boolean {
    return (FIXED_GROUP_KEYS as readonly string[]).includes(key);
}

/** The weeks, months and years of a time group's key (`2026-03`, `2026`, a day, a Monday), for the viewer's locale; `short` leaves the year off a day, for an axis. */
export function bucketLabel(key: string, bucket: ReportBucket | undefined, locale: string, short = false): string {
    const parts = key.split('-').map(Number);
    try {
        if (bucket === 'year' || /^\d{4}$/.test(key)) return String(parts[0]);
        if (bucket === 'month' || /^\d{4}-\d{2}$/.test(key)) return new Intl.DateTimeFormat(locale, short ? { month: 'short', year: '2-digit', timeZone: 'UTC' } : { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(parts[0], parts[1] - 1, 1)));
        return new Intl.DateTimeFormat(locale, short ? { day: 'numeric', month: 'short', timeZone: 'UTC' } : { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(parts[0], parts[1] - 1, parts[2])));
    } catch {
        return key;
    }
}
