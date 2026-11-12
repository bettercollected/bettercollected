/**
 * Saved views of a report: opening one (its definition becomes the report in the
 * address) and telling whether the report on screen still is it. The address holds
 * the working report (filters and cards); a saved view is the definition the server
 * stored, so the two meet here.
 */
import { ReportCardDef, ReportClause, ReportDefinition, ReportFilters, ReportView } from '@app/utils/report';
import { ResponseListState } from '@app/utils/response-list-state';

const two = (value: number) => String(value).padStart(2, '0');

/** The viewer's calendar day (`YYYY-MM-DD`) an instant falls on, `shift` days later. */
export function localDay(instant: string, shift = 0): string | undefined {
    const moment = new Date(instant);
    if (Number.isNaN(moment.getTime())) return undefined;
    const day = new Date(moment.getFullYear(), moment.getMonth(), moment.getDate() + shift);
    return `${day.getFullYear()}-${two(day.getMonth() + 1)}-${two(day.getDate())}`;
}

/** The cards of a stored definition as the page holds them (nothing but ids, kinds, dimensions and measures). */
export function cardsOf(definition: ReportDefinition): ReportCardDef[] {
    return (definition.cards ?? []).map(({ id, kind, dimension, measures, title }) => ({ id, kind, ...(dimension ? { dimension } : {}), measures, ...(title ? { title } : {}) }));
}

/** The list filters of a stored definition, as the viewer's calendar days (the first day, and the last one: the stored end is exclusive). */
export function filtersOf(definition: ReportDefinition): Pick<ResponseListState, 'from' | 'to' | 'status' | 'who' | 'version'> {
    const filters = definition.filters ?? {};
    const state: Pick<ResponseListState, 'from' | 'to' | 'status' | 'who' | 'version'> = {};
    const from = filters.submittedFrom ? localDay(filters.submittedFrom) : undefined;
    const to = filters.submittedTo ? localDay(filters.submittedTo, -1) : undefined;
    if (from) state.from = from;
    if (to && (!from || to >= from)) state.to = to;
    const status = filters.status?.[0];
    if (status === 'none' || status === 'pending' || status === 'declined') state.status = status;
    if (filters.respondent === 'anonymous' || filters.respondent === 'known') state.who = filters.respondent;
    const version = filters.formVersion?.[0];
    if (typeof version === 'number' && version > 0) state.version = version;
    return state;
}

/** The conditions on answers a stored definition holds. */
export function whereOf(definition: ReportDefinition): ReportClause[] {
    return (definition.filters?.where ?? []).map(({ field, op, value }) => ({ field, op, ...(value === undefined || value === null ? {} : { value }) }));
}

function filterKey(filters: ReportFilters | undefined) {
    const value = filters ?? {};
    const instant = (iso?: string) => (iso ? new Date(iso).getTime() : null);
    return {
        from: instant(value.submittedFrom),
        to: instant(value.submittedTo),
        status: [...(value.status ?? [])].sort(),
        respondent: value.respondent ?? null,
        versions: [...(value.formVersion ?? [])].sort((a, b) => a - b),
        // the order of the conditions is not part of what they say
        where: (value.where ?? []).map((clause) => JSON.stringify([clause.field, clause.op, clause.value ?? null])).sort()
    };
}

function cardKey(card: ReportCardDef) {
    return { id: card.id, kind: card.kind, dimension: card.dimension ? { field: card.dimension.field, bucket: card.dimension.bucket ?? null } : null, measures: card.measures.map((m) => ({ agg: m.agg, field: m.field ?? null })) };
}

/** What the working report and a stored one are compared by: the cards (not their titles) and the filters (as instants); the zone is the viewer's, not the view's. */
export function comparable(cards: ReportCardDef[], filters: ReportFilters | undefined): string {
    return JSON.stringify({ cards: cards.map(cardKey), filters: filterKey(filters) });
}

/** Whether the report on screen differs from what the view stored. */
export function isModified(view: ReportView, cards: ReportCardDef[], filters: ReportFilters): boolean {
    return comparable(cardsOf(view.definition), view.definition.filters) !== comparable(cards, filters);
}

/** A `view` parameter that could be an id (the server stores object ids): anything else is no view. */
export const VIEW_ID = /^[0-9a-f]{24}$/;
