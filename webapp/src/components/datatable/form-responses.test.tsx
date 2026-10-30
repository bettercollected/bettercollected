import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The "server": one list of responses, filtered like the backend does for
// `dataOwnerIdentifier`. Every call the component makes is recorded.
type Item = { responseId: string; dataOwnerIdentifier: string | null; answers: any; createdAt: string };
const server: { items: Item[]; error: boolean; calls: any[]; refetchCalls: any[] } = { items: [], error: false, calls: [], refetchCalls: [] };

vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetFormsSubmissionsQuery: (arg: any, options: any) => {
            // refetch re-renders, like RTK Query does when it asks again
            const [, setTick] = React.useState(0);
            const refetch = () => {
                server.refetchCalls.push(arg);
                setTick((tick) => tick + 1);
            };
            server.calls.push({ arg, options });
            if (options?.skip) return { data: undefined, isLoading: false, isFetching: false, isError: false, refetch };
            if (server.error) return { data: undefined, isLoading: false, isFetching: false, isError: true, refetch };
            const term = arg.dataOwnerIdentifier;
            const items = term ? server.items.filter((item) => (item.dataOwnerIdentifier ?? '').includes(term)) : server.items;
            // pages of `arg.size` rows, like the backend
            const pages = Math.max(1, Math.ceil(items.length / arg.size));
            return { data: { items: items.slice((arg.page - 1) * arg.size, arg.page * arg.size), total: items.length, page: arg.page, pages, size: arg.size }, isLoading: false, isFetching: false, isError: false, refetch };
        },
        useLazyExportFormSubmissionsQuery: () => [vi.fn(), { isLoading: false }],
        useLazyGetWorkspaceSubmissionQuery: () => [vi.fn()],
        useLazyGetWorkspaceFormVersionQuery: () => [vi.fn()],
        useGetWorkspacePermissionsQuery: () => ({ data: { permissions: [] }, isLoading: false, isError: false })
    };
});

import { FieldTypes } from '@app/models/dtos/form';
import I18nProvider from '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import FormResponsesTable from './form-responses';

const FIELD = { id: 'q1', type: FieldTypes.SHORT_TEXT, title: 'Favourite colour' };
const item = (id: string, owner: string | null, colour: string): Item => ({ responseId: id, dataOwnerIdentifier: owner, answers: { q1: { field: { id: 'q1' }, type: FieldTypes.SHORT_TEXT, text: colour } }, createdAt: '2026-01-02T03:04:05Z' });

const renderTable = (props: any = {}) =>
    render(
        <ReduxProvider store={store}>
            <I18nProvider>
                <FormResponsesTable props={{ formId: 'form-1', workspace: { id: 'workspace-1' }, isSubmission: true, ...props }} />
            </I18nProvider>
        </ReduxProvider>
    );

const search = (text: string) => {
    fireEvent.change(screen.getByPlaceholderText('Search by responder email'), { target: { value: text } });
    // SearchInput debounces by 500 ms
    act(() => {
        vi.advanceTimersByTime(600);
    });
};

const lastQuery = () => server.calls.filter((call) => !call.options?.skip).at(-1)?.arg;

describe('responses table: search and honest states', () => {
    beforeEach(() => {
        // jsdom has no matchMedia; react-data-table-component asks for it
        window.matchMedia = ((query: string) => ({ matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false, onchange: null })) as any;
        vi.useFakeTimers();
        server.error = false;
        server.calls = [];
        server.refetchCalls = [];
        server.items = [item('r1', 'known.a@example.com', 'blue'), item('r2', 'known.b@example.com', 'green'), item('r3', 'other@example.com', 'red'), item('r4', null, 'pink')];
        store.dispatch(setWorkspace({ id: 'workspace-1' } as any));
        store.dispatch(setForm({ formId: 'form-1', title: 'Colours', responses: 4, deletionRequests: 0, version: 1, builderVersion: 'v1', settings: { provider: 'google' }, fields: [FIELD] } as any));
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('lists every response before anything is typed, with the new placeholder', () => {
        renderTable();
        expect(screen.getByPlaceholderText('Search by responder email')).toBeInTheDocument();
        expect(screen.getByText('known.a@example.com')).toBeInTheDocument();
        expect(screen.getByText('other@example.com')).toBeInTheDocument();
        expect(screen.getByText('blue')).toBeInTheDocument();
        expect(lastQuery()).toMatchObject({ formId: 'form-1', workspaceId: 'workspace-1', page: 1 });
        expect(lastQuery()).not.toHaveProperty('dataOwnerIdentifier');
    });

    it('sends the search text and the table shows only the rows that query returns', () => {
        renderTable();
        search('known');
        expect(lastQuery()).toMatchObject({ dataOwnerIdentifier: 'known', page: 1 });
        expect(screen.getByText('known.a@example.com')).toBeInTheDocument();
        expect(screen.getByText('known.b@example.com')).toBeInTheDocument();
        expect(screen.queryByText('other@example.com')).toBeNull();
    });

    it('asks for the first page again whenever the search changes', () => {
        server.items = Array.from({ length: 40 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
        renderTable();
        fireEvent.click(screen.getByLabelText(/next/i));
        expect(lastQuery().page).toBe(2);
        search('person1');
        expect(lastQuery()).toMatchObject({ dataOwnerIdentifier: 'person1', page: 1 });
    });

    it('says "No responses match" for a search with no hits, not "No responses yet"', () => {
        renderTable();
        search('nobody');
        expect(screen.getByText('No responses match')).toBeInTheDocument();
        expect(screen.getByText(/Nothing matches/)).toHaveTextContent('nobody');
        expect(screen.queryByText('No responses yet')).toBeNull();
        // the search box stays so it can be changed
        expect(screen.getByPlaceholderText('Search by responder email')).toBeInTheDocument();
    });

    it('goes back to the full list when the search is cleared', () => {
        renderTable();
        search('nobody');
        search('');
        expect(screen.getByText('other@example.com')).toBeInTheDocument();
        expect(lastQuery()).not.toHaveProperty('dataOwnerIdentifier');
    });

    it('says "No responses yet" only when the form has none', () => {
        server.items = [];
        store.dispatch(setForm({ ...store.getState().form, responses: 0 } as any));
        renderTable();
        expect(screen.getByText('No responses yet')).toBeInTheDocument();
        expect(screen.queryByText('No responses match')).toBeNull();
    });

    it('shows an error with Retry for a failed or refused request, never "No responses yet"', () => {
        server.error = true;
        renderTable();
        expect(screen.getByRole('alert')).toHaveTextContent('Could not load responses');
        expect(screen.queryByText('No responses yet')).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
        expect(server.refetchCalls).toHaveLength(1);
    });

    it('retries with the current search, keeping the typed text', () => {
        renderTable();
        search('known');
        server.error = true;
        search('known.a');
        expect(screen.getByText('Could not load responses')).toBeInTheDocument();
        expect((screen.getByPlaceholderText('Search by responder email') as HTMLInputElement).value).toBe('known.a');
        fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
        expect(server.refetchCalls.at(-1)).toMatchObject({ dataOwnerIdentifier: 'known.a', page: 1 });
    });

    it('retries the page that failed', () => {
        server.items = Array.from({ length: 40 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
        renderTable();
        server.error = true;
        fireEvent.click(screen.getByLabelText(/next/i));
        expect(screen.getByText('Could not load responses')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
        expect(server.refetchCalls.at(-1)).toMatchObject({ page: 2 });
    });

    it('recovers after an error: the rows come back when the retry succeeds', () => {
        server.error = true;
        renderTable();
        expect(screen.getByText('Could not load responses')).toBeInTheDocument();
        server.error = false;
        fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
        expect(screen.queryByText('Could not load responses')).toBeNull();
        expect(screen.getByText('known.a@example.com')).toBeInTheDocument();
    });

    it('clearing the search after an error goes back to the full list', () => {
        renderTable();
        search('known');
        server.error = true;
        search('known.a');
        expect(screen.getByText('Could not load responses')).toBeInTheDocument();
        server.error = false;
        search('');
        expect(screen.queryByText('Could not load responses')).toBeNull();
        expect(screen.getByText('other@example.com')).toBeInTheDocument();
        expect(lastQuery()).not.toHaveProperty('dataOwnerIdentifier');
    });

    it('a no-match search after paging starts from page 1 and clearing it lists page 1 again', () => {
        server.items = Array.from({ length: 40 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
        renderTable();
        fireEvent.click(screen.getByLabelText(/next/i));
        expect(lastQuery().page).toBe(2);
        search('nobody');
        expect(lastQuery()).toMatchObject({ dataOwnerIdentifier: 'nobody', page: 1 });
        expect(screen.getByText('No responses match')).toBeInTheDocument();
        search('');
        expect(lastQuery()).toMatchObject({ page: 1 });
        expect(screen.getByText('person0@example.com')).toBeInTheDocument();
    });

    it('shows the loader, not "No responses yet", while there is no workspace to ask', () => {
        store.dispatch(setWorkspace({} as any));
        renderTable({ workspace: {} });
        expect(screen.getByRole('status', { name: 'Loading responses' })).toBeInTheDocument();
        expect(screen.queryByText('No responses yet')).toBeNull();
        expect(screen.queryByText('Could not load responses')).toBeNull();
    });

    it('uses the deletion-request wording on the deletion requests page', () => {
        store.dispatch(setForm({ ...store.getState().form, deletionRequests: 2 } as any));
        server.items = [item('r1', 'known.a@example.com', 'blue')];
        renderTable({ requestForDeletion: true, isSubmission: false });
        search('zzz');
        expect(screen.getByText('No deletion requests match')).toBeInTheDocument();
    });
});
