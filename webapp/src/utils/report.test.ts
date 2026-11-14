import { describe, expect, it } from 'vitest';

import { catalogue } from '@app/test/report-fixtures';
import {
    ReportCardDef,
    bucketLabel,
    canDonut,
    cardProblem,
    cardsParam,
    fixedGroups,
    kindsFor,
    overviewCards,
    parseCardsParam,
    reportDefinition,
    reportErrorOf,
    reportFilters
} from '@app/utils/report';

const card = (changes: Partial<ReportCardDef> = {}): ReportCardDef => ({ id: 'c1', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }], ...changes });

describe('the Overview', () => {
    it('starts with the response count and the responses over time, then one card per reportable question', () => {
        const cards = overviewCards(catalogue);
        expect(cards.slice(0, 2).map((c) => [c.id, c.kind, c.dimension?.field])).toEqual([
            ['total', 'tile', undefined],
            ['time', 'line', 'submitted_at']
        ]);
        // a choice, checkboxes, a rating and yes/no are bars of counts; a number is its average
        expect(cards.slice(2).map((c) => [c.kind, c.dimension?.field ?? c.measures[0].field, c.measures[0].agg])).toEqual([
            ['bar', 'q:team', 'count'],
            ['bar', 'q:tools', 'count'],
            ['bar', 'q:score', 'count'],
            ['tile', 'q:years', 'avg'],
            ['bar', 'q:remote', 'count']
        ]);
    });

    it('lists the first twelve questions, or all of them up to the card limit', () => {
        const many = { ...catalogue, fields: Array.from({ length: 30 }, (_, index) => ({ ...catalogue.fields[0], key: `q:f${index}` })) };
        expect(overviewCards(many)).toHaveLength(2 + 12);
        expect(overviewCards(many, true)).toHaveLength(24);
    });

    it('is a report the server accepts: every card passes the same checks', () => {
        for (const c of overviewCards(catalogue)) expect(cardProblem(c, catalogue)).toBeUndefined();
    });
});

describe('what a card may be', () => {
    it('allows a donut only for a dimension with at most six groups it can count', () => {
        // four options plus "Other" and "Removed option": six
        expect(fixedGroups(catalogue, 'q:team')).toBe(6);
        expect(canDonut(catalogue, 'q:team')).toBe(true);
        expect(canDonut(catalogue, 'q:remote')).toBe(true);
        expect(canDonut(catalogue, 'respondent')).toBe(true);
        // checkboxes, a rating, the form version and the submission time are not parts of a whole
        for (const key of ['q:tools', 'q:score', 'form_version', 'submitted_at', 'feedback_status']) expect(canDonut(catalogue, key)).toBe(false);
        const seven = { ...catalogue, fields: [{ ...catalogue.fields[0], options: Array.from({ length: 5 }, (_, i) => ({ id: `o${i}`, label: `O${i}` })) }] };
        expect(canDonut(seven, 'q:team')).toBe(false);
    });

    it('offers kinds by what the card is grouped by', () => {
        expect(kindsFor(catalogue, undefined)).toEqual(['tile', 'table']);
        expect(kindsFor(catalogue, 'submitted_at')).toEqual(['line', 'bar', 'table']);
        expect(kindsFor(catalogue, 'q:team')).toEqual(['bar', 'donut', 'table']);
        expect(kindsFor(catalogue, 'q:tools')).toEqual(['bar', 'table']);
    });

    it('names why a card cannot be asked for', () => {
        expect(cardProblem(card({ dimension: { field: 'q:gone' } }), catalogue)).toBe('unknown');
        expect(cardProblem(card({ measures: [{ agg: 'avg', field: 'q:gone' }] }), catalogue)).toBe('unknown');
        expect(cardProblem(card({ kind: 'line' }), catalogue)).toBe('invalid');
        expect(cardProblem(card({ kind: 'donut', dimension: { field: 'q:tools' } }), catalogue)).toBe('invalid');
        expect(cardProblem(card({ measures: [{ agg: 'avg', field: 'q:team' }] }), catalogue)).toBe('invalid');
        expect(cardProblem(card({ measures: [{ agg: 'count', field: 'q:score' }] }), catalogue)).toBe('invalid');
        expect(cardProblem(card({ dimension: { field: 'q:years' } }), catalogue)).toBe('invalid');
        expect(cardProblem(card({ measures: [] }), catalogue)).toBe('invalid');
        expect(cardProblem(card(), catalogue)).toBeUndefined();
    });
});

describe('the report in the address', () => {
    const cards: ReportCardDef[] = [card(), { id: 'c2', kind: 'tile', measures: [{ agg: 'avg', field: 'q:years' }] }, { id: 'c3', kind: 'line', dimension: { field: 'submitted_at', bucket: 'week' }, measures: [{ agg: 'count' }] }];

    it('round-trips the cards, with only ids, built-in names and enums in it', () => {
        const value = cardsParam(cards);
        expect(value).toMatch(/^[A-Za-z0-9_-]+$/);
        expect(parseCardsParam(value)).toEqual(cards);
    });

    it('reads nothing malformed: it is the Overview', () => {
        const bad = (value: unknown) => parseCardsParam(btoa(JSON.stringify(value)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''));
        expect(parseCardsParam(null)).toBeUndefined();
        expect(parseCardsParam('')).toBeUndefined();
        expect(parseCardsParam('%%%')).toBeUndefined();
        expect(parseCardsParam('x'.repeat(7000))).toBeUndefined();
        // each of these would parse as a card if one rule were missing
        expect(bad([{ id: 'a', kind: 'bar', measures: [{ agg: 'count' }] }])).toEqual([{ id: 'a', kind: 'bar', measures: [{ agg: 'count' }] }]);
        expect(bad({ not: 'a list' })).toBeUndefined();
        expect(bad([{ id: 'a', kind: 'pie', measures: [{ agg: 'count' }] }])).toBeUndefined();
        expect(bad([{ id: 'a', kind: 'bar', measures: [{ agg: 'median' }] }])).toBeUndefined();
        expect(bad([{ id: 'a', kind: 'bar', measures: [] }])).toBeUndefined();
        expect(bad([{ id: 'a b', kind: 'bar', measures: [{ agg: 'count' }] }])).toBeUndefined();
        expect(bad([{ id: 'a', kind: 'bar', measures: [{ agg: 'count', field: '<script>' }] }])).toBeUndefined();
        expect(bad([{ id: 'a', kind: 'bar', dimension: { field: 'q:x', bucket: 'decade' }, measures: [{ agg: 'count' }] }])).toBeUndefined();
        // the same id twice
        expect(parseCardsParam(cardsParam([card(), card()]))).toBeUndefined();
        // more cards than a report may hold
        expect(parseCardsParam(cardsParam(Array.from({ length: 25 }, (_, i) => card({ id: `c${i}` }))))).toBeUndefined();
    });

    it('drops anything but the definition from a card when it writes it', () => {
        const parsed = parseCardsParam(cardsParam([{ ...card(), title: 'Typed text' } as ReportCardDef]));
        expect(parsed?.[0]).not.toHaveProperty('title');
    });
});

describe('the definition asked for', () => {
    it('turns the list filters into the API ones (viewer days into UTC instants, a version into a list)', () => {
        const day = (value: string, add = 0) => `${value}+${add}`;
        expect(reportFilters({ from: '2026-10-01', to: '2026-10-31', status: 'none', who: 'known', version: 2 }, day)).toEqual({
            submittedFrom: '2026-10-01+0',
            submittedTo: '2026-10-31+1',
            status: ['none'],
            respondent: 'known',
            formVersion: [2]
        });
        expect(reportFilters({}, day)).toEqual({});
        expect(reportDefinition([card()], {}, 'Europe/Amsterdam')).toEqual({ v: 1, filters: {}, tz: 'Europe/Amsterdam', cards: [card()] });
    });
});

describe('errors', () => {
    it('reads the code, count and cap of a refusal', () => {
        expect(reportErrorOf({ status: 413, data: { code: 'too_many_rows', count: 25000, max: 20000, message: 'x' } })).toEqual({ status: 413, code: 'too_many_rows', count: 25000, max: 20000 });
        expect(reportErrorOf({ status: 429, data: { code: 'report_busy' } }).code).toBe('report_busy');
        expect(reportErrorOf({ status: 'FETCH_ERROR' })).toEqual({ status: undefined, code: undefined, count: undefined, max: undefined });
        expect(reportErrorOf(undefined).code).toBeUndefined();
    });
});

describe('time group labels', () => {
    it('names a day, a month and a year in the viewer language', () => {
        expect(bucketLabel('2026-03', 'month', 'en')).toBe('Mar 2026');
        expect(bucketLabel('2026-03', 'month', 'nl')).toMatch(/mrt/i);
        expect(bucketLabel('2026', 'year', 'en')).toBe('2026');
        expect(bucketLabel('2026-03-09', 'day', 'en')).toBe('Mar 9, 2026');
        expect(bucketLabel('garbage', 'day', 'en')).toBeTruthy();
    });
});
