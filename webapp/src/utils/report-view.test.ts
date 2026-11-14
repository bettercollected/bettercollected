import i18n from 'i18next';
import { afterEach, describe, expect, it } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { catalogue, cardFigures } from '@app/test/report-fixtures';
import { ReportCardDef } from '@app/utils/report';
import { buildCardView, cardTitle, chartSummary } from '@app/utils/report-view';

const t = (key: string, options?: Record<string, unknown>) => i18n.t(key, options) as string;
const card = (changes: Partial<ReportCardDef> = {}): ReportCardDef => ({ id: 'c1', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }], ...changes });
const view = (def: ReportCardDef, locale = 'en') => buildCardView(def, cardFigures(def), catalogue, t, locale);

afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('a card view', () => {
    it('lists the groups with their value and share of the answered responses, without the empty "Other" and "Removed option"', () => {
        const v = view(card());
        expect(v.rows.map((r) => [r.label, r.valueText, r.shareText])).toEqual([
            ['North', '74', '37%'],
            ['South', '52', '26%'],
            ['East', '41', '21%'],
            ['West', '31', '16%']
        ]);
        expect(v.title).toBe('Which team are you in?');
        expect(v.basis).toBe('198 of 212 answered');
    });

    it('titles a tile, a time series and a figure by their meaning', () => {
        expect(cardTitle({ id: 'a', kind: 'tile', measures: [{ agg: 'count' }] }, catalogue, t)).toBe('Responses');
        expect(cardTitle({ id: 'a', kind: 'line', dimension: { field: 'submitted_at' }, measures: [{ agg: 'count' }] }, catalogue, t)).toBe('Responses over time');
        expect(cardTitle({ id: 'a', kind: 'tile', measures: [{ agg: 'avg', field: 'q:years' }] }, catalogue, t)).toBe('Average · Years at the organisation');
        expect(cardTitle(card({ title: 'Mine' }), catalogue, t)).toBe('Mine');
    });

    it('says the fixed groups in the viewer language, not the server English', async () => {
        await i18n.changeLanguage('nl');
        const remote = view(card({ dimension: { field: 'q:remote' } }), 'nl');
        expect(remote.rows.map((r) => r.label)).toEqual(['Ja', 'Nee']);
        const who = view(card({ dimension: { field: 'respondent' } }), 'nl');
        expect(who.rows.map((r) => r.label)).toEqual(['Anoniem', 'Geïdentificeerd']);
        const versions = view(card({ dimension: { field: 'form_version' } }), 'nl');
        expect(versions.rows[0].label).toBe('Versie 1');
        expect(view(card(), 'nl').basis).toBe('198 van 212 beantwoord');
    });

    it('formats numbers in the locale: a decimal comma in Dutch', () => {
        const tile: ReportCardDef = { id: 't', kind: 'tile', measures: [{ agg: 'avg', field: 'q:years' }] };
        expect(view(tile).headline).toBe('7.4');
        expect(view(tile, 'nl').headline).toBe('7,4');
    });

    it('draws a donut as a bar when it has more than six slices or is not a count', () => {
        expect(view(card({ kind: 'donut', dimension: { field: 'q:remote' } })).kind).toBe('donut');
        const many = buildCardView(card({ kind: 'donut', dimension: { field: 'q:score' } }), { ...cardFigures(card({ dimension: { field: 'q:score' } })), groups: Array.from({ length: 7 }, (_, i) => ({ key: String(i), label: String(i), n: 1, values: [1], valueN: [1] })) }, catalogue, t, 'en');
        expect(many.kind).toBe('bar');
        expect(view({ id: 'a', kind: 'donut', dimension: { field: 'q:remote' }, measures: [{ agg: 'avg', field: 'q:years' }] }).kind).toBe('bar');
    });

    it('marks a card nobody answered as empty, and a card with no figures as not ready', () => {
        const none = { ...cardFigures(card()), answered: 0, skipped: 212 };
        expect(buildCardView(card(), none, catalogue, t, 'en').empty).toBe(true);
        expect(buildCardView(card(), undefined, catalogue, t, 'en').empty).toBe(false);
    });

    it('names the cut-off groups of a long list', () => {
        const long = { ...cardFigures(card()), otherGroups: { n: 12, count: 3 }, truncated: true };
        const v = buildCardView(card(), long, catalogue, t, 'en');
        expect(v.otherGroups).toEqual({ n: 12, count: 3, label: 'Other groups (3)' });
        expect(v.truncated).toBe(true);
    });
});

describe('the sentence a screen reader gets', () => {
    it('names the kind, the number of groups and the largest one, and points at the table', () => {
        expect(chartSummary(view(card()), t)).toBe('Bar chart with 4 groups. Largest: North, 74 (37%). The figures are in the table that follows.');
    });

    it('speaks a time series from its first to its last point', () => {
        const line = view({ id: 'l', kind: 'line', dimension: { field: 'submitted_at', bucket: 'day' }, measures: [{ agg: 'count' }] });
        expect(chartSummary(line, t)).toMatch(/^Line chart with 30 points, from Oct 1, 2026 to Oct 30, 2026\. Highest: .*\. The figures are in the table that follows\.$/);
    });

    it('reads a tile as its title and figure', () => {
        expect(chartSummary(view({ id: 't', kind: 'tile', measures: [{ agg: 'count' }] }), t)).toBe('Responses: 212');
    });
});
