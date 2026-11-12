// One card of a report, each kind: what it prints (values written out, never colour alone), the table it can be read as,
// the sentence and table a screen reader gets, keyboard reach, and axe.
import React from 'react';

import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';
import { cardFigures, catalogue } from '@app/test/report-fixtures';
import { ReportCardDef } from '@app/utils/report';

import ReportCard from './report-card';

const bar: ReportCardDef = { id: 'team', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }] };
const donut: ReportCardDef = { id: 'remote', kind: 'donut', dimension: { field: 'q:remote' }, measures: [{ agg: 'count' }] };
const line: ReportCardDef = { id: 'time', kind: 'line', dimension: { field: 'submitted_at', bucket: 'day' }, measures: [{ agg: 'count' }] };
const columns: ReportCardDef = { id: 'months', kind: 'line', dimension: { field: 'submitted_at', bucket: 'month' }, measures: [{ agg: 'count' }] };
const tile: ReportCardDef = { id: 'total', kind: 'tile', measures: [{ agg: 'count' }] };
const average: ReportCardDef = { id: 'years', kind: 'tile', measures: [{ agg: 'avg', field: 'q:years' }] };
const table: ReportCardDef = { id: 'tools', kind: 'table', dimension: { field: 'q:tools' }, measures: [{ agg: 'count' }] };

// (no user-event in this repo: the events a pointer or a select sends)
const userEvent = {
    setup: () => ({
        click: async (element: Element) => {
            fireEvent.click(element);
        },
        selectOptions: async (element: Element, value: string) => {
            fireEvent.change(element, { target: { value } });
        }
    })
};

const renderCard = (def: ReportCardDef, props: Partial<React.ComponentProps<typeof ReportCard>> = {}) => {
    const handlers = { onChange: vi.fn(), onRemove: vi.fn(), onMove: vi.fn() };
    const view = render(<ReportCard def={def} result={cardFigures(def)} catalogue={catalogue} first={false} last={false} {...handlers} {...props} />);
    return { ...view, ...handlers };
};

describe('a number tile', () => {
    it('prints the figure large, with its basis, and is one image described by a sentence', () => {
        renderCard(tile);
        const figure = screen.getByRole('figure', { name: 'Responses' });
        expect(within(figure).getByText('n = 212')).toBeInTheDocument();
        const image = within(figure).getByRole('img', { name: 'Responses: chart. A table with the same figures follows.' });
        expect(image).toHaveTextContent('212');
        expect(document.getElementById(image.getAttribute('aria-describedby') as string)).toHaveTextContent('Responses: 212');
    });

    it('shows an average with the number of answers it is of', () => {
        renderCard(average);
        expect(screen.getByRole('figure', { name: 'Average · Years at the organisation' })).toHaveTextContent('7.4');
        expect(screen.getByText('198 of 212 answered')).toBeInTheDocument();
    });
});

describe('a bar chart', () => {
    it('writes every value and share beside its bar', () => {
        renderCard(bar);
        const figure = screen.getByRole('figure', { name: 'Which team are you in?' });
        const image = within(figure).getByRole('img');
        for (const text of ['North', '74 (37%)', 'South', '52 (26%)', 'East', 'West', '31 (16%)']) expect(image).toHaveTextContent(text.replace(/[()]/g, (c) => c));
        // the empty "Other" and "Removed option" are not listed
        expect(image).not.toHaveTextContent('Removed option');
    });

    it('says the checkbox counts add up to more than the responses', () => {
        renderCard({ id: 'tools', kind: 'bar', dimension: { field: 'q:tools' }, measures: [{ agg: 'count' }] });
        expect(screen.getByText(/add up to more than the number of responses/)).toBeInTheDocument();
    });
});

describe('a donut', () => {
    it('lists each slice with its value and share in a legend, and draws a pattern for every slice after the first', () => {
        const { container } = renderCard(donut);
        const figure = screen.getByRole('figure', { name: 'Do you work remotely?' });
        expect(figure).toHaveTextContent('Yes');
        expect(figure).toHaveTextContent('96 (48%)');
        expect(figure).toHaveTextContent('No');
        expect(container.querySelectorAll('pattern')).toHaveLength(2);
        // the second slice is told apart by a line pattern as well as by its colour
        expect(container.querySelector('pattern line')).toBeTruthy();
    });
});

describe('a line over time', () => {
    it('labels the first, last and highest points, and lists every day in the table', () => {
        const { container } = renderCard(line);
        const figure = screen.getByRole('figure', { name: 'Responses over time' });
        expect(container.querySelector('polyline')).toBeTruthy();
        expect(container.querySelectorAll('svg text').length).toBeGreaterThan(4);
        fireEvent.click(within(figure).getByRole('button', { name: 'Show as table' }));
        expect(within(figure).getAllByRole('row')).toHaveLength(31);
    });

    it('is columns, each with its value, for a few points', () => {
        const { container } = renderCard(columns);
        expect(container.querySelector('polyline')).toBeNull();
        expect(container.querySelectorAll('rect[style*="series-1"]')).toHaveLength(6);
        const values = Array.from(container.querySelectorAll('svg text')).map((node) => node.textContent);
        expect(values.filter((text) => /^\d+$/.test(text ?? '')).length).toBeGreaterThanOrEqual(6);
    });
});

describe('a table card', () => {
    it('is a table with captioned columns and no switch', () => {
        renderCard(table);
        const figure = screen.getByRole('figure', { name: 'Which tools do you use?' });
        const grid = within(figure).getByRole('table', { name: 'Which tools do you use?' });
        expect(within(grid).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Which tools do you use?', 'Responses', 'Share']);
        expect(within(grid).getByRole('row', { name: /Mail/ })).toHaveTextContent('180');
        expect(within(figure).queryByRole('button', { name: /Show as/ })).toBeNull();
    });
});

describe('the table alternative', () => {
    it('is in the page for a screen reader behind every chart, and a button swaps the chart for it', async () => {
        const user = userEvent.setup();
        renderCard(bar);
        const figure = screen.getByRole('figure', { name: 'Which team are you in?' });
        // the table is there (visually hidden) while the chart shows
        expect(within(figure).getByRole('table', { name: 'Which team are you in?' })).toBeInTheDocument();
        expect(within(figure).getByRole('img')).toBeInTheDocument();
        const toggle = within(figure).getByRole('button', { name: 'Show as table' });
        await user.click(toggle);
        expect(within(figure).queryByRole('img')).toBeNull();
        expect(within(figure).getByRole('table')).toBeInTheDocument();
        const back = within(figure).getByRole('button', { name: 'Show as chart' });
        expect(back).toBeInTheDocument();
        await user.click(back);
        expect(within(figure).getByRole('img')).toBeInTheDocument();
    });

    it('is reached by keyboard: the toggle is a real button in the tab order, and no mark is a tab stop', () => {
        const { container } = renderCard(bar);
        const toggle = screen.getByRole('button', { name: 'Show as table' });
        toggle.focus();
        expect(toggle).toHaveFocus();
        expect(toggle.tagName).toBe('BUTTON');
        expect(toggle).not.toHaveAttribute('tabindex', '-1');
        // nothing in the chart takes focus: the table is the way in
        expect(container.querySelectorAll('svg [tabindex], [role="img"] [tabindex]')).toHaveLength(0);
        // the card's own controls are all buttons, in reading order: change, up, down, remove, then the switch
        const names = screen.getAllByRole('button').map((button) => button.getAttribute('aria-label') ?? button.textContent);
        expect(names).toEqual(['Change Which team are you in?', 'Move Which team are you in? up', 'Move Which team are you in? down', 'Remove Which team are you in?', 'Show as table']);
    });

    it('lists an average beside the number of responses it is of', async () => {
        const user = userEvent.setup();
        renderCard({ id: 'a', kind: 'bar', dimension: { field: 'q:score' }, measures: [{ agg: 'avg', field: 'q:score' }] });
        await user.click(screen.getByRole('button', { name: 'Show as table' }));
        const grid = screen.getByRole('table');
        expect(within(grid).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['How satisfied are you?', 'Average · How satisfied are you?', 'Responses']);
    });
});

describe('states', () => {
    it('says "No answers yet." for a card nobody answered', () => {
        renderCard(bar, { result: { ...cardFigures(bar), answered: 0, skipped: 212 } });
        expect(screen.getByText('No answers yet.')).toBeInTheDocument();
        expect(screen.queryByRole('img')).toBeNull();
    });

    it('says the question is gone, with the controls to remove the card', async () => {
        const user = userEvent.setup();
        const { onRemove } = renderCard({ ...bar, dimension: { field: 'q:gone' } }, { result: undefined });
        expect(screen.getByText('This question is no longer in the form.')).toBeInTheDocument();
        await user.click(screen.getByRole('button', { name: 'Remove q:gone' }));
        expect(onRemove).toHaveBeenCalled();
    });

    it('says the figures are loading, in words', () => {
        renderCard(bar, { result: undefined, loading: true });
        expect(screen.getByText('Loading figures')).toBeInTheDocument();
    });

    it('moves and removes by buttons named after the card; the ends cannot move further', async () => {
        const user = userEvent.setup();
        const { onMove, onRemove } = renderCard(bar, { first: true });
        expect(screen.getByRole('button', { name: 'Move Which team are you in? up' })).toBeDisabled();
        await user.click(screen.getByRole('button', { name: 'Move Which team are you in? down' }));
        expect(onMove).toHaveBeenCalledWith(1);
        await user.click(screen.getByRole('button', { name: 'Remove Which team are you in?' }));
        expect(onRemove).toHaveBeenCalled();
    });

    it('changes what a card shows through labelled selects, applied together', async () => {
        const user = userEvent.setup();
        const { onChange } = renderCard(bar);
        await user.click(screen.getByRole('button', { name: 'Change Which team are you in?' }));
        const form = screen.getByRole('form', { name: 'Add a card' });
        await user.selectOptions(within(form).getByLabelText('Group by'), 'q:remote');
        await user.selectOptions(within(form).getByLabelText('Show as'), 'donut');
        expect(onChange).not.toHaveBeenCalled();
        await user.click(within(form).getByRole('button', { name: 'Done' }));
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ id: 'team', kind: 'donut', dimension: { field: 'q:remote' }, measures: [{ agg: 'count' }] }));
    });

    it('takes an average of a question, which leaves out the donut and asks which question', async () => {
        const user = userEvent.setup();
        const { onChange } = renderCard(tile);
        await user.click(screen.getByRole('button', { name: 'Change Responses' }));
        const form = screen.getByRole('form', { name: 'Add a card' });
        await user.selectOptions(within(form).getByLabelText('Show'), 'avg');
        expect(within(form).getByLabelText('Question')).toBeInTheDocument();
        await user.selectOptions(within(form).getByLabelText('Question'), 'q:years');
        expect(within(form).queryByRole('option', { name: 'Donut' })).toBeNull();
        await user.click(within(form).getByRole('button', { name: 'Done' }));
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ kind: 'tile', measures: [{ agg: 'avg', field: 'q:years' }] }));
    });
});

describe('axe', () => {
    it.each([
        ['tile', tile],
        ['average', average],
        ['bar', bar],
        ['donut', donut],
        ['line', line],
        ['columns', columns],
        ['table', table]
    ])('finds no WCAG A or AA violation in a %s card, as a chart and as a table', async (_name, def) => {
        const { container } = renderCard(def);
        expect(await axeViolations(container)).toEqual([]);
        const toggle = screen.queryByRole('button', { name: 'Show as table' });
        if (toggle) {
            fireEvent.click(toggle);
            expect(await axeViolations(container)).toEqual([]);
        }
    });

    it('finds none with the editor open', async () => {
        const { container } = renderCard(bar);
        fireEvent.click(screen.getByRole('button', { name: 'Change Which team are you in?' }));
        expect(await axeViolations(container)).toEqual([]);
    });
});


describe('negative values and big numbers', () => {
    const scored = (values: number[], card: ReportCardDef) => ({
        ...cardFigures(card),
        answered: 100,
        groups: values.map((value, index) => ({ key: String(index + 1), label: String(index + 1), n: 10, values: [value], valueN: [10] }))
    });
    const average: ReportCardDef = { id: 'a', kind: 'bar', dimension: { field: 'q:score' }, measures: [{ agg: 'avg', field: 'q:score' }] };

    it('draws no bar for a value of zero or below, and still prints it', () => {
        const { container } = renderCard(average, { result: scored([4, -3, 0, 2], average) });
        const bars = Array.from(container.querySelectorAll('rect[style*="series-1"]'));
        // a bar for 4 and for 2 only, none of them of a negative or empty width
        expect(bars).toHaveLength(2);
        expect(bars.every((bar) => Number(bar.getAttribute('width')) > 0)).toBe(true);
        expect(container.querySelector('[role="img"]')).toHaveTextContent('-3');
    });

    const series = (): ReportCardDef => ({ id: 'l', kind: 'line', dimension: { field: 'submitted_at', bucket: 'month' }, measures: [{ agg: 'count' }] });
    const run = (values: number[], card: ReportCardDef) =>
        renderCard(card, {
            result: {
                ...cardFigures(card),
                groups: values.map((value, index) => ({ key: `2026-${String(index + 1).padStart(2, '0')}`, label: `m${index}`, n: 1, values: [value], valueN: [1] }))
            }
        });

    it('runs the axis of columns below zero for a negative value, with the column on the other side of the zero line', () => {
        const { container } = run([6, -4, 2], series());
        const ticks = Array.from(container.querySelectorAll('svg line')).map((line) => Number(line.getAttribute('y1')));
        // the three grid lines run from the lowest tick, through zero, to the highest
        const zeroLine = ticks[1];
        const columns = Array.from(container.querySelectorAll('rect[style*="series-1"]'));
        expect(columns).toHaveLength(3);
        const [up, down] = columns;
        // the positive column ends on the zero line, the negative one starts there
        expect(Number(up.getAttribute('y')) + Number(up.getAttribute('height'))).toBeCloseTo(zeroLine, 0);
        expect(Number(down.getAttribute('y'))).toBeCloseTo(zeroLine, 0);
        // and the axis names its lowest tick
        const labels = Array.from(container.querySelectorAll('svg text')).map((node) => node.textContent);
        expect(labels).toContain('-5');
        expect(labels).toContain('0');
        expect(labels).toContain('10');
    });

    it('keeps a line with a negative value inside its plot', () => {
        const values = Array.from({ length: 20 }, (_, index) => (index % 2 ? -7 : 5));
        const card: ReportCardDef = { id: 'l', kind: 'line', dimension: { field: 'submitted_at', bucket: 'day' }, measures: [{ agg: 'count' }] };
        const { container } = renderCard(card, {
            result: { ...cardFigures(card), groups: values.map((value, index) => ({ key: `2026-10-${String(index + 1).padStart(2, '0')}`, label: `d${index}`, n: 1, values: [value], valueN: [1] })) }
        });
        const line = container.querySelector('polyline') as SVGPolylineElement;
        const ys = (line.getAttribute('points') as string).split(' ').map((pair) => Number(pair.split(',')[1]));
        // the plot is 224 high with margins of 22 above and 36 below
        expect(Math.min(...ys)).toBeGreaterThanOrEqual(22);
        expect(Math.max(...ys)).toBeLessThanOrEqual(224 - 36);
    });

    it('writes the total in the middle of a donut in the viewer locale', () => {
        const big: ReportCardDef = { id: 'big', kind: 'donut', dimension: { field: 'q:remote' }, measures: [{ agg: 'count' }] };
        const result = { ...cardFigures(big), answered: 12340, groups: [{ key: 'yes', label: 'Yes', n: 9000, values: [9000], valueN: [9000] }, { key: 'no', label: 'No', n: 3340, values: [3340], valueN: [3340] }] };
        const { container } = renderCard(big, { result });
        const centre = () => Array.from(container.querySelectorAll('svg text')).map((node) => node.textContent);
        expect(centre()).toContain('12,340');
    });
});


describe('opening the responses behind a group', () => {
    const drillable: ReportCardDef = { id: 'team', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }] };

    it('puts a button on each row of the table, named after the group, and none while the chart shows', () => {
        const onDrill = vi.fn();
        renderCard(drillable, { onDrill });
        const figure = screen.getByRole('figure', { name: 'Which team are you in?' });
        // the table behind the chart (for a screen reader) has no buttons: nothing in a chart is a tab stop
        expect(within(figure).queryByRole('button', { name: /Open these responses/ })).toBeNull();
        fireEvent.click(within(figure).getByRole('button', { name: 'Show as table' }));
        fireEvent.click(within(figure).getByRole('button', { name: 'Open these responses: South' }));
        expect(onDrill).toHaveBeenCalledTimes(1);
        expect(onDrill.mock.calls[0][0]).toEqual(drillable);
        expect(onDrill.mock.calls[0][1]).toMatchObject({ key: 'south', label: 'South', n: 52 });
    });

    it('is reached by keyboard, in order, as buttons of the table', () => {
        renderCard(drillable, { onDrill: vi.fn() });
        fireEvent.click(screen.getByRole('button', { name: 'Show as table' }));
        const names = screen.getAllByRole('button', { name: /^Open these responses/ }).map((b) => b.getAttribute('aria-label'));
        expect(names).toEqual(['Open these responses: North', 'Open these responses: South', 'Open these responses: East', 'Open these responses: West']);
    });

    it('is offered on a table card too, and not for a group nobody is in', () => {
        const table: ReportCardDef = { ...drillable, kind: 'table', dimension: { field: 'q:remote' } };
        const result = cardFigures(table);
        renderCard(table, { onDrill: vi.fn(), result: { ...result, groups: [...result.groups, { key: 'maybe', label: 'Maybe', n: 0, values: [0], valueN: [0] }] } });
        expect(screen.getAllByRole('button', { name: /^Open these responses/ })).toHaveLength(2);
    });

    it('is not offered for a card without groups, for a status the pass does not read, or without a handler', () => {
        const tileView = renderCard({ id: 't', kind: 'tile', measures: [{ agg: 'count' }] }, { onDrill: vi.fn() });
        fireEvent.click(screen.getByRole('button', { name: 'Show as table' }));
        expect(screen.queryByRole('button', { name: /Open these responses/ })).toBeNull();
        tileView.unmount();
        const status: ReportCardDef = { id: 's', kind: 'table', dimension: { field: 'status' }, measures: [{ agg: 'count' }] };
        const statusView = renderCard(status, { onDrill: vi.fn(), result: { ...cardFigures(status), groups: [{ key: 'none', label: 'None', n: 5, values: [5], valueN: [5] }] } });
        expect(screen.queryByRole('button', { name: /Open these responses/ })).toBeNull();
        statusView.unmount();
        renderCard({ ...drillable, kind: 'table' });
        expect(screen.queryByRole('button', { name: /Open these responses/ })).toBeNull();
    });

    it('finds no axe violation in a table with the buttons', async () => {
        const { container } = renderCard(drillable, { onDrill: vi.fn() });
        fireEvent.click(screen.getByRole('button', { name: 'Show as table' }));
        expect(await axeViolations(container)).toEqual([]);
    });
});
