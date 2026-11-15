// Per-answer colours (the Pigment theme): each answer of a choice question keeps its series colour across bar and donut
// cards and filters, by its position among the options; the sixth option and later, "Other", a removed option and "no
// answer" take the neutral; other questions and other kinds keep today's colours; what is printed never changes.
import React from 'react';

import i18n from 'i18next';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { cardFigures, catalogue } from '@app/test/report-fixtures';
import { ReportCardDef, ReportCardResult, ReportCatalogue } from '@app/utils/report';
import { buildCardView } from '@app/utils/report-view';

import { BarChart, DataTable, DonutChart, rowColour } from './charts';

const t = (key: string, options?: Record<string, unknown>) => i18n.t(key, options) as string;
const card = (changes: Partial<ReportCardDef> = {}): ReportCardDef => ({ id: 'c1', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }], ...changes });
const view = (def: ReportCardDef, perAnswer: boolean, result: ReportCardResult | undefined = cardFigures(def), cat: ReportCatalogue = catalogue) => buildCardView(def, result, cat, t, 'en', { perAnswer });

const group = (key: string, label: string, n: number) => ({ key, label, n, values: [n], valueN: [n] });
const result = (def: ReportCardDef, groups: ReturnType<typeof group>[]): ReportCardResult => ({ id: def.id, n: 100, answered: 100, skipped: 0, multiple: false, groups, otherGroups: { n: 0, count: 0 }, truncated: false });

// a question with seven options, the sixth and seventh past the colours there are
const wide: ReportCatalogue = {
    ...catalogue,
    fields: [
        ...catalogue.fields,
        {
            key: 'q:seven',
            label: 'Which room?',
            kind: 'choice',
            dimension: true,
            measures: ['count'],
            versions: [1],
            inCurrentVersion: true,
            options: ['a', 'b', 'c', 'd', 'e', 'f', 'g'].map((id) => ({ id, label: id.toUpperCase() }))
        }
    ]
};
const SEVEN = card({ dimension: { field: 'q:seven' } });
const sevenFigures = result(SEVEN, [group('a', 'A', 20), group('b', 'B', 18), group('c', 'C', 16), group('d', 'D', 14), group('e', 'E', 12), group('f', 'F', 8), group('g', 'G', 6), group('other', 'Other', 4), group('removed', 'Removed option', 2)]);

const colours = (v: ReturnType<typeof view>) => Object.fromEntries(v.rows.map((row, index) => [row.key, rowColour(v, row, index, v.kind === 'donut')]));
const swatches = (container: HTMLElement) => [...container.querySelectorAll('ul[aria-hidden] svg rect')].map((rect) => rect.getAttribute('style')?.match(/url\(["']?#([^)"']+)/)?.[1]).map((id) => container.querySelector(`pattern[id="${id}"] > rect`)?.getAttribute('style')?.match(/fill:\s*([^;]+)/)?.[1]?.trim());

describe('a card that gives each answer its colour', () => {
    it('colours the answers of a choice question by their position among the options, the series tokens in order', () => {
        const v = view(card(), true);
        expect(v.perAnswer).toBe(true);
        expect(colours(v)).toEqual({ north: 'var(--series-1)', south: 'var(--series-2)', east: 'var(--series-3)', west: 'var(--series-4)' });
        expect(Object.values(colours(v)).join(' ')).not.toMatch(/pig|#/);
    });

    it('gives the sixth option and later, "Other", a removed option and "no answer" the neutral', () => {
        const v = view(SEVEN, true, sevenFigures, wide);
        expect(colours(v)).toEqual({
            a: 'var(--series-1)',
            b: 'var(--series-2)',
            c: 'var(--series-3)',
            d: 'var(--series-4)',
            e: 'var(--series-5)',
            f: 'var(--viz-neutral)',
            g: 'var(--viz-neutral)',
            other: 'var(--viz-neutral)',
            removed: 'var(--viz-neutral)'
        });
        const none = view(card(), true, result(card(), [group('north', 'North', 60), group('none', 'No answer', 40)]));
        expect(colours(none)).toEqual({ north: 'var(--series-1)', none: 'var(--viz-neutral)' });
        // a group the question no longer has an option for
        expect(colours(view(card(), true, result(card(), [group('gone', 'Gone', 5)])))).toEqual({ gone: 'var(--viz-neutral)' });
    });

    it('keeps an answer\'s colour when a filter leaves out the answers before it, and on a card of another kind', () => {
        const full = colours(view(card(), true));
        const filtered = colours(view(card(), true, result(card(), [group('east', 'East', 9), group('west', 'West', 4)])));
        expect(filtered).toEqual({ east: full.east, west: full.west });
        const asDonut = colours(view(card({ kind: 'donut' }), true));
        expect(asDonut).toEqual(full);
        // the same answer on another card of the same question
        expect(colours(view(card({ id: 'c2', kind: 'donut', filter: undefined } as Partial<ReportCardDef>), true, result(card(), [group('south', 'South', 7), group('north', 'North', 3)])))).toEqual({ south: full.south, north: full.north });
    });

    it('draws the bars of a card in those colours, and the bars of a Daybreak card in one blue as before', () => {
        const pigment = render(<BarChart view={view(card(), true)} summaryId="s" label="l" locale="en" />).container;
        expect([...pigment.querySelectorAll('rect[data-answer-colour]')].map((rect) => rect.getAttribute('data-answer-colour'))).toEqual(['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)']);
        const daybreak = render(<BarChart view={view(card(), false)} summaryId="s" label="l" locale="en" />).container;
        expect([...daybreak.querySelectorAll('rect[data-answer-colour]')].map((rect) => rect.getAttribute('data-answer-colour'))).toEqual(['var(--series-1)', 'var(--series-1)', 'var(--series-1)', 'var(--series-1)']);
    });

    it('gives an answer the same colour on a bar card and on a donut card, with the pattern still following the position', () => {
        const bars = render(<BarChart view={view(card(), true)} summaryId="s" label="l" locale="en" />).container;
        const donut = render(<DonutChart view={view(card({ kind: 'donut' }), true)} summaryId="s" label="l" locale="en" />).container;
        const barColours = [...bars.querySelectorAll('rect[data-answer-colour]')].map((rect) => rect.getAttribute('data-answer-colour'));
        expect(swatches(donut)).toEqual(barColours);
        // patterns by position, as today: one per row, all different from the first on
        const patterns = [...donut.querySelectorAll('pattern')].map((pattern) => pattern.innerHTML);
        expect(new Set(patterns).size).toBe(4);
    });

    it('leaves a Daybreak donut with the series in turn and its patterns as they were', () => {
        const donut = render(<DonutChart view={view(card({ kind: 'donut' }), false)} summaryId="s" label="l" locale="en" />).container;
        expect(swatches(donut)).toEqual(['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)']);
    });
});

describe('position carries the identity, so colour is a second cue', () => {
    it('lists the answers in the order of the question\'s options, which is the order of the colours, with the neutral ones last', () => {
        const v = view(SEVEN, true, sevenFigures, wide);
        expect(v.rows.map((row) => row.key)).toEqual(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'other', 'removed']);
        const positions = v.rows.filter((row) => row.colour !== undefined).map((row) => row.colour);
        expect(positions).toEqual([0, 1, 2, 3, 4]);
        // every answer after the coloured ones is a neutral one
        expect(v.rows.slice(5).every((row) => row.colour === undefined)).toBe(true);
        // the card does not reorder what the server sent (by the form's option order)
        const reversed = result(SEVEN, [...sevenFigures.groups].reverse());
        expect(view(SEVEN, true, reversed, wide).rows.map((row) => row.key)).toEqual(['removed', 'other', 'g', 'f', 'e', 'd', 'c', 'b', 'a']);
    });

    it('draws the track under every bar and the fill as long as its value says, so a bar reads by length and by the printed value without its colour', () => {
        const { container } = render(<BarChart view={view(card(), true)} summaryId="s" label="l" locale="en" />);
        const bars = [...container.querySelectorAll('li')].map((item) => {
            const rects = item.querySelectorAll('svg rect');
            return { track: rects[0].getAttribute('width'), fill: Number(rects[1]?.getAttribute('width') ?? 0), text: item.textContent };
        });
        expect(bars.map((bar) => bar.track)).toEqual(['100', '100', '100', '100']);
        // 74, 52, 41 and 31 of the largest: the lengths fall in the order of the values
        expect(bars.map((bar) => Math.round(bar.fill))).toEqual([100, 70, 55, 42]);
        expect(bars.map((bar) => bar.text)).toEqual(['North74 (37%)', 'South52 (26%)', 'East41 (21%)', 'West31 (16%)']);
    });
});

describe('what keeps one colour', () => {
    it.each([
        ['a yes/no question', card({ kind: 'donut', dimension: { field: 'q:remote' } })],
        ['a rating question', card({ dimension: { field: 'q:score' } })],
        ['a time series', card({ kind: 'line', dimension: { field: 'submitted_at', bucket: 'day' } })],
        ['a number tile', card({ kind: 'tile', dimension: undefined })],
        ['a table', card({ kind: 'table' })],
        ['a built-in grouping', card({ dimension: { field: 'respondent' } })]
    ])('%s is not coloured per answer, even in the Pigment theme', (_, def) => {
        const v = view(def, true);
        expect(v.perAnswer).toBe(false);
        expect(v.rows.every((row) => row.colour === undefined)).toBe(true);
        expect(view(def, false)).toEqual(v);
        for (const [index, row] of v.rows.entries()) expect(rowColour(v, row, index, v.kind === 'donut')).toBe(v.kind === 'donut' ? `var(--series-${index + 1})` : 'var(--series-1)');
    });

    it('is the default: a card built without the option is exactly the Daybreak card', () => {
        const def = card();
        expect(buildCardView(def, cardFigures(def), catalogue, t, 'en')).toEqual(view(def, false));
    });
});

describe('what is printed does not depend on colour', () => {
    it('shows the same labels, values and shares, and the same table, in either theme', () => {
        const strip = (v: ReturnType<typeof view>) => ({ ...v, perAnswer: undefined, rows: v.rows.map(({ colour: _colour, ...rest }) => rest) });
        expect(strip(view(card(), true))).toEqual(strip(view(card(), false)));
        const a = render(<DataTable view={view(card(), true)} caption="c" />).container.innerHTML;
        const b = render(<DataTable view={view(card(), false)} caption="c" />).container.innerHTML;
        expect(a).toBe(b);
    });

    it('prints every value beside its mark in the bars and the donut, so colour is never the only way to tell answers apart', () => {
        const bars = render(<BarChart view={view(card(), true)} summaryId="s" label="l" locale="en" />).container.textContent ?? '';
        for (const text of ['North', '74 (37%)', 'South', '52 (26%)', 'East', '41 (21%)', 'West', '31 (16%)']) expect(bars).toContain(text);
        const donut = render(<DonutChart view={view(card({ kind: 'donut' }), true)} summaryId="s" label="l" locale="en" />).container.textContent ?? '';
        for (const text of ['North', '74 (37%)', 'West', '31 (16%)']) expect(donut).toContain(text);
    });
});
