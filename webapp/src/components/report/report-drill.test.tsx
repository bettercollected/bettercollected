// Drill-down: the responses behind a group, a page at a time, each linking to its own page; the cursor, a short page when the
// search budget ended, the errors, the link to the responses list, and axe, in English and Dutch.
import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';
import { ReportDefinition, ReportDrillPage, ReportDrillRow } from '@app/utils/report';

import ReportDrill from './report-drill';

const api = vi.hoisted(() => ({ load: vi.fn() }));
vi.mock('@app/store/workspaces/api', () => ({ useGetReportResponsesMutation: () => [api.load] }));
vi.mock('next/link', () => ({ default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a> }));

const definition: ReportDefinition = { v: 1, filters: {}, tz: 'UTC', cards: [{ id: 'team', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }] }] };
const row = (n: number, changes: Partial<ReportDrillRow> = {}): ReportDrillRow => ({ id: `resp-${n}`, submittedAt: `2026-10-${String(n).padStart(2, '0')}T10:30:00Z`, formVersion: 2, respondent: n % 2 ? 'anonymous' : 'known', ...changes });
const page = (rows: ReportDrillRow[], changes: Partial<ReportDrillPage> = {}): ReportDrillPage => ({ responses: rows, cursor: null, scanned: rows.length, exhausted: true, ...changes });
const reply = (value: ReportDrillPage) => ({ unwrap: () => Promise.resolve(value) });
const refuse = (status: number, code?: string) => ({ unwrap: () => Promise.reject({ status, data: code ? { code } : undefined }) });

const onClose = vi.fn();
const renderDrill = (props: Partial<React.ComponentProps<typeof ReportDrill>> = {}) =>
    render(<ReportDrill workspaceId="ws" workspaceName="voorbeeld" formId="form 1" definition={definition} cardId="team" group={{ key: 'north', label: 'North' }} onClose={onClose} {...props} />);

beforeEach(() => {
    api.load.mockReset();
    onClose.mockReset();
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('the first page', () => {
    it('asks for the group of the card with the definition on screen, and lists each response with a link to its page', async () => {
        api.load.mockReturnValue(reply(page([row(1), row(2)])));
        renderDrill();
        expect(await screen.findByRole('table', { name: 'Responses in North' })).toBeInTheDocument();
        expect(api.load).toHaveBeenCalledWith({ workspaceId: 'ws', formId: 'form 1', definition, card: 'team', group: 'north', cursor: null, size: 25 });
        const rows = screen.getAllByRole('row').slice(1);
        expect(rows).toHaveLength(2);
        // the time in the viewer's locale, the version, who (never an address), and a link by the response id
        expect(within(rows[0]).getByText(/(1 Oct 2026|Oct 1, 2026)/)).toBeInTheDocument();
        expect(within(rows[0]).getByText('Anonymous')).toBeInTheDocument();
        expect(within(rows[1]).getByText('Identified')).toBeInTheDocument();
        const link = within(rows[0]).getByRole('link');
        expect(link).toHaveAttribute('href', '/voorbeeld/dashboard/forms/form%201/responses/resp-1');
        expect(link.getAttribute('aria-label')).toMatch(/^Open the response submitted /);
        expect(screen.getByRole('status')).toHaveTextContent('2 responses shown.');
        // the heading has the focus, so a screen reader starts there
        expect(screen.getByRole('heading', { name: 'Responses in North' })).toHaveFocus();
    });

    it('says a group nobody is in has no responses', async () => {
        api.load.mockReturnValue(reply(page([])));
        renderDrill();
        expect(await screen.findByText('No responses in this group.')).toBeInTheDocument();
        expect(screen.queryByRole('table')).toBeNull();
        expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    });

    it('says it is loading, in words', () => {
        api.load.mockReturnValue({ unwrap: () => new Promise(() => undefined) });
        renderDrill();
        expect(screen.getByRole('status')).toHaveTextContent('Loading figures');
    });
});

describe('more pages', () => {
    it('shows more from the cursor of the last page and ends when the set does', async () => {
        api.load.mockReturnValueOnce(reply(page(Array.from({ length: 25 }, (_, i) => row(i + 1)), { cursor: 'c1', exhausted: false })));
        renderDrill();
        const more = await screen.findByRole('button', { name: 'Show more' });
        api.load.mockReturnValueOnce(reply(page([row(26), row(27)])));
        fireEvent.click(more);
        await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(28));
        expect(api.load).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: 'c1' }));
        expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
        expect(screen.getByRole('status')).toHaveTextContent('27 responses shown.');
    });

    it('says the search stopped before the end when a short page comes with a cursor, and offers to go on', async () => {
        api.load.mockReturnValue(reply(page([row(1)], { cursor: 'c9', exhausted: false, scanned: 20000 })));
        renderDrill();
        expect(await screen.findByText(/The search stopped before the end of the responses; show more to continue\./)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Show more' })).toBeInTheDocument();
    });

    it('starts again when the group, the card or the definition changes, and drops the answer of the one it left', async () => {
        let release: (value: ReportDrillPage) => void = () => undefined;
        api.load.mockReturnValueOnce({ unwrap: () => new Promise<ReportDrillPage>((resolve) => (release = resolve)) });
        const { rerender } = renderDrill();
        api.load.mockReturnValueOnce(reply(page([row(5)])));
        rerender(<ReportDrill workspaceId="ws" workspaceName="voorbeeld" formId="form 1" definition={definition} cardId="team" group={{ key: 'south', label: 'South' }} onClose={onClose} />);
        expect(await screen.findByRole('table', { name: 'Responses in South' })).toBeInTheDocument();
        // the first group's answer arrives late and is not shown
        release(page([row(1), row(2), row(3)]));
        await new Promise((resolve) => setTimeout(resolve, 10));
        expect(screen.getAllByRole('row')).toHaveLength(2);
    });
});

describe('refusals', () => {
    it.each([
        [429, 'rate_limited', 'Too many report requests in a short time. Try again in a moment.'],
        [429, 'report_busy', 'Other reports are being computed. Try again in a moment.'],
        [503, 'report_timeout', 'This report took too long to compute. Narrow the dates or the form version, or try again.'],
        [500, undefined, 'The figures could not be loaded.']
    ])('%s %s: says so and retries the same page', async (status, code, text) => {
        api.load.mockReturnValueOnce(refuse(status, code));
        renderDrill();
        const alert = await screen.findByRole('alert');
        expect(alert).toHaveTextContent(text);
        api.load.mockReturnValueOnce(reply(page([row(1)])));
        fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
        expect(await screen.findByRole('table')).toBeInTheDocument();
        expect(api.load).toHaveBeenCalledTimes(2);
        expect(api.load).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: null }));
    });
});

describe('the list, closing and language', () => {
    it('links to the responses list when it can say the same group, and closes', async () => {
        api.load.mockReturnValue(reply(page([row(1)])));
        renderDrill({ listHref: '/voorbeeld/dashboard/forms/form%201/responses?version=2' });
        expect(await screen.findByRole('link', { name: 'Open this group in the responses list' })).toHaveAttribute('href', '/voorbeeld/dashboard/forms/form%201/responses?version=2');
        fireEvent.click(screen.getByRole('button', { name: 'Close the list of responses' }));
        expect(onClose).toHaveBeenCalled();
    });

    it('offers no list link for a group the list cannot say', async () => {
        api.load.mockReturnValue(reply(page([row(1)])));
        renderDrill();
        await screen.findByRole('table');
        expect(screen.queryByRole('link', { name: 'Open this group in the responses list' })).toBeNull();
    });

    it('is in Dutch', async () => {
        await i18n.changeLanguage('nl');
        api.load.mockReturnValue(reply(page([row(1)], { cursor: 'c', exhausted: false })));
        renderDrill({ group: { key: 'north', label: 'Noord' } });
        expect(await screen.findByRole('table', { name: 'Reacties in Noord' })).toBeInTheDocument();
        expect(screen.getByText('Anoniem')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Toon meer' })).toBeInTheDocument();
        expect(screen.getByRole('status')).toHaveTextContent('1 reacties getoond.');
    });

    it('finds no axe violation, with rows, with an error and empty', async () => {
        api.load.mockReturnValueOnce(reply(page([row(1), row(2)], { cursor: 'c', exhausted: false })));
        const { container, unmount } = renderDrill({ listHref: '/x' });
        await screen.findByRole('table');
        expect(await axeViolations(container)).toEqual([]);
        unmount();
        api.load.mockReturnValueOnce(refuse(500));
        const failed = renderDrill();
        await screen.findByRole('alert');
        expect(await axeViolations(failed.container)).toEqual([]);
        failed.unmount();
        api.load.mockReturnValueOnce(reply(page([])));
        const empty = renderDrill();
        await screen.findByText('No responses in this group.');
        expect(await axeViolations(empty.container)).toEqual([]);
    });
});
