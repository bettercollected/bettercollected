import { describe, expect, it } from 'vitest';

import { catalogue } from '@app/test/report-fixtures';
import { ReportCardDef, ReportDefinition, ReportView, overviewCards } from '@app/utils/report';
import { VIEW_ID, cardsOf, comparable, filtersOf, isModified, localDay } from '@app/utils/report-views';

const bar: ReportCardDef = { id: 'c1', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }] };

const stored = (changes: Partial<ReportDefinition> = {}): ReportDefinition => ({ v: 1, filters: {}, tz: 'UTC', cards: [bar], ...changes });
const view = (definition: ReportDefinition): ReportView => ({ id: 'a'.repeat(24), name: 'Weekly', scope: 'private', mine: true, ownerName: null, revision: 1, createdAt: null, updatedAt: null, definition, canEdit: true, canDelete: true });

describe('a saved definition on screen', () => {
    it('gives its cards back as the page holds them', () => {
        expect(cardsOf(stored())).toEqual([bar]);
        // what the server adds (default and empty fields) is not a card's
        const withExtras = stored({ cards: [{ ...bar, extra: 1 } as ReportCardDef] });
        expect(cardsOf(withExtras)).toEqual([bar]);
    });

    it('turns the stored filters into the list filters in the viewer calendar: the stored end is exclusive', () => {
        const from = new Date(2026, 9, 1).toISOString();
        const to = new Date(2026, 10, 1).toISOString();
        expect(filtersOf(stored({ filters: { submittedFrom: from, submittedTo: to, status: ['none'], respondent: 'known', formVersion: [2] } }))).toEqual({
            from: '2026-10-01',
            to: '2026-10-31',
            status: 'none',
            who: 'known',
            version: 2
        });
        expect(filtersOf(stored())).toEqual({});
    });

    it('ignores what the list has no filter for, and never an end before the start', () => {
        const instant = (day: number) => new Date(2026, 9, day).toISOString();
        expect(filtersOf(stored({ filters: { status: ['bogus'], respondent: 'someone', formVersion: [-3] } }))).toEqual({});
        expect(filtersOf(stored({ filters: { submittedFrom: instant(20), submittedTo: instant(5) } }))).toEqual({ from: '2026-10-20' });
    });

    it('names a calendar day, and nothing for text that is no instant', () => {
        expect(localDay(new Date(2026, 2, 9, 15).toISOString())).toBe('2026-03-09');
        expect(localDay(new Date(2026, 2, 9, 15).toISOString(), -1)).toBe('2026-03-08');
        expect(localDay('garbage')).toBeUndefined();
    });
});

describe('whether the report on screen is still the view', () => {
    it('is not modified by the server\'s spelling of the same filters', () => {
        const from = new Date(2026, 9, 1);
        const definition = stored({ filters: { submittedFrom: from.toISOString().replace('.000Z', 'Z'), status: [], formVersion: [] } });
        expect(isModified(view(definition), [bar], { submittedFrom: from.toISOString() })).toBe(false);
    });

    it('notices a changed card, an added card, a moved card, another filter and another dimension', () => {
        const saved = view(stored({ cards: overviewCards(catalogue).slice(0, 3) }));
        const same = overviewCards(catalogue).slice(0, 3);
        expect(isModified(saved, same, {})).toBe(false);
        expect(isModified(saved, same.slice(0, 2), {})).toBe(true);
        expect(isModified(saved, [...same].reverse(), {})).toBe(true);
        expect(isModified(saved, [...same.slice(0, 2), { ...same[2], kind: 'table' }], {})).toBe(true);
        expect(isModified(saved, [...same.slice(0, 2), { ...same[2], dimension: { field: 'q:remote' } }], {})).toBe(true);
        expect(isModified(saved, same, { respondent: 'known' })).toBe(true);
    });

    it('does not compare a card\'s title, the zone or the order of a list of versions', () => {
        expect(comparable([{ ...bar, title: 'A' }], { formVersion: [2, 1] })).toBe(comparable([{ ...bar, title: 'B' }], { formVersion: [1, 2] }));
    });
});

describe('the view in the address', () => {
    it('is an object id and nothing else', () => {
        expect(VIEW_ID.test('a'.repeat(24))).toBe(true);
        for (const bad of ['', 'x'.repeat(24), 'a'.repeat(23), 'A'.repeat(24), '../../etc', 'a'.repeat(24) + '#']) expect(VIEW_ID.test(bad)).toBe(false);
    });
});
