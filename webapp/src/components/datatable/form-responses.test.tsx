import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The "server": one list of responses, filtered like the backend does for
// `dataOwnerIdentifier`. Every call the component makes is recorded.
type Item = { responseId: string; dataOwnerIdentifier: string | null; answers: any; createdAt: string };
// `pending`: the server has not answered yet. Like RTK Query, the hook then
// reports isFetching with the data of the last answer it got (none after an
// error): isLoading is only true for a first load that never failed.
const server: { items: Item[]; error: boolean; pending: boolean; lastData: any; calls: any[]; refetchCalls: any[]; openResponse: ReturnType<typeof vi.fn> } = {
    items: [],
    error: false,
    pending: false,
    lastData: undefined,
    calls: [],
    refetchCalls: [],
    openResponse: vi.fn()
};

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
            if (server.pending) return { data: server.lastData, isLoading: false, isFetching: true, isError: false, refetch };
            if (server.error) {
                server.lastData = undefined;
                return { data: undefined, isLoading: false, isFetching: false, isError: true, refetch };
            }
            const term = arg.dataOwnerIdentifier;
            const items = term ? server.items.filter((item) => (item.dataOwnerIdentifier ?? '').includes(term)) : server.items;
            // pages of `arg.size` rows, like the backend
            const pages = Math.max(1, Math.ceil(items.length / arg.size));
            server.lastData = { items: items.slice((arg.page - 1) * arg.size, arg.page * arg.size), total: items.length, page: arg.page, pages, size: arg.size };
            return { data: server.lastData, isLoading: false, isFetching: false, isError: false, refetch };
        },
        useLazyExportFormSubmissionsQuery: () => [vi.fn(), { isLoading: false }],
        useLazyGetWorkspaceSubmissionQuery: () => [(arg: any) => server.openResponse(arg)],
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

const tree = (props: any = {}) => (
    <ReduxProvider store={store}>
        <I18nProvider>
            <FormResponsesTable props={{ formId: 'form-1', workspace: { id: 'workspace-1' }, isSubmission: true, ...props }} />
        </I18nProvider>
    </ReduxProvider>
);
const renderTable = (props: any = {}) => render(tree(props));

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
        server.pending = false;
        server.lastData = undefined;
        server.calls = [];
        server.refetchCalls = [];
        server.openResponse = vi.fn(() => Promise.resolve({ data: undefined }));
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

    describe('nothing to show while the server is still answering', () => {
        it('a Retry after a failed first load shows the loader, not "No responses yet"', () => {
            server.error = true;
            renderTable();
            expect(screen.getByText('Could not load responses')).toBeInTheDocument();
            server.error = false;
            server.pending = true;
            fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
            expect(screen.getByRole('status', { name: 'Loading responses' })).toBeInTheDocument();
            expect(screen.queryByText('No responses yet')).toBeNull();
            expect(screen.queryByText('Could not load responses')).toBeNull();
        });

        it('moves focus to the results after Retry instead of dropping it on <body>', () => {
            server.error = true;
            renderTable();
            server.error = false;
            server.pending = true;
            const retry = screen.getByRole('button', { name: 'Retry' });
            retry.focus();
            fireEvent.click(retry);
            expect(document.activeElement).not.toBe(document.body);
            expect(document.activeElement).toBe(screen.getByRole('region', { name: 'Responses' }));
        });

        it('clearing a no-match search shows the loader until the full list arrives, not "No responses yet"', () => {
            const { rerender } = renderTable();
            search('nobody');
            expect(screen.getByText('No responses match')).toBeInTheDocument();
            server.pending = true;
            search('');
            expect(screen.getByRole('status', { name: 'Loading responses' })).toBeInTheDocument();
            expect(screen.queryByText('No responses yet')).toBeNull();
            expect(screen.queryByText('No responses match')).toBeNull();
            // the server answers
            server.pending = false;
            rerender(tree());
            expect(screen.getByText('other@example.com')).toBeInTheDocument();
        });

        it('a new search after a no-match one does not say "Nothing matches" the new text before the server answered', () => {
            renderTable();
            search('nobody');
            server.pending = true;
            search('known');
            expect(screen.getByRole('status', { name: 'Loading responses' })).toBeInTheDocument();
            expect(screen.queryByText(/Nothing matches/)).toBeNull();
        });

        it('keeps the rows on screen, marked busy, while a search with earlier rows is asking', () => {
            renderTable();
            server.pending = true;
            search('known');
            expect(screen.getByText('other@example.com').closest('[aria-busy="true"]')).not.toBeNull();
        });
    });

    describe('a later page that empties', () => {
        const many = (count: number) => Array.from({ length: count }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));

        it('steps back to the last page that still has rows, keeping the pagination', () => {
            // 31 rows: three pages of 15, 15 and 1
            server.items = many(31);
            const { rerender } = renderTable();
            fireEvent.click(screen.getByLabelText(/next/i));
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(lastQuery().page).toBe(3);
            expect(screen.getByText('person30@example.com')).toBeInTheDocument();
            // the last row on page 3 is deleted
            server.items = many(30);
            rerender(tree());
            expect(lastQuery().page).toBe(2);
            expect(screen.getByText('person15@example.com')).toBeInTheDocument();
            expect(screen.getByLabelText(/next/i)).toBeInTheDocument();
            expect(screen.queryByText('No responses yet')).toBeNull();
        });

        it('says "No responses yet" only once the whole form has none', () => {
            server.items = many(16);
            const { rerender } = renderTable();
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(lastQuery().page).toBe(2);
            server.items = [];
            rerender(tree());
            expect(lastQuery().page).toBe(1);
            expect(screen.getByText('No responses yet')).toBeInTheDocument();
        });

        it('steps back on the deletion-requests tab too, never "No deletion requests" while some remain', () => {
            store.dispatch(setForm({ ...store.getState().form, deletionRequests: 16 } as any));
            server.items = many(16);
            const { rerender } = renderTable({ requestForDeletion: true, isSubmission: false });
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(lastQuery().page).toBe(2);
            // the request on page 2 is closed
            server.items = many(15);
            rerender(tree({ requestForDeletion: true, isSubmission: false }));
            expect(lastQuery()).toMatchObject({ page: 1, requestedForDeletionOly: true });
            expect(screen.getByText('person0@example.com')).toBeInTheDocument();
            expect(screen.queryByText('No deletion requests')).toBeNull();
        });

        it('a failed later page stays an error instead of stepping back', () => {
            server.items = many(16);
            renderTable();
            server.error = true;
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(screen.getByText('Could not load responses')).toBeInTheDocument();
            expect(lastQuery().page).toBe(2);
        });
    });

    it('joins the options of a multi-select answer with ", "', () => {
        const hobbies = { id: 'q2', type: FieldTypes.MULTIPLE_CHOICE, title: 'Hobbies', properties: { allowMultipleSelection: true, choices: [{ id: 'c1', value: 'Reading' }, { id: 'c2', value: 'Cycling' }] } };
        store.dispatch(setForm({ ...store.getState().form, fields: [FIELD, hobbies] } as any));
        server.items = [{ ...item('r1', 'known.a@example.com', 'blue'), answers: { q1: { field: { id: 'q1' }, type: FieldTypes.SHORT_TEXT, text: 'blue' }, q2: { field: { id: 'q2' }, type: FieldTypes.MULTIPLE_CHOICE, choices: { values: ['c1', 'c2'] } } } }];
        renderTable();
        expect(screen.getByText('Reading, Cycling')).toBeInTheDocument();
        expect(screen.queryByText('Reading,Cycling')).toBeNull();
    });

    describe('keyboard and screen reader basics', () => {
        it('labels the search box', () => {
            renderTable();
            expect(screen.getByRole('textbox', { name: 'Search responses by responder email' })).toBeInTheDocument();
        });

        it('labels the search box for deletion requests on that tab', () => {
            store.dispatch(setForm({ ...store.getState().form, deletionRequests: 2 } as any));
            renderTable({ requestForDeletion: true, isSubmission: false });
            expect(screen.getByRole('textbox', { name: 'Search deletion requests by responder email' })).toBeInTheDocument();
            expect(screen.queryByRole('textbox', { name: 'Search responses by responder email' })).toBeNull();
        });

        it('opens a response from a real button named "Open response"', () => {
            renderTable();
            const buttons = screen.getAllByRole('button', { name: 'Open response' });
            expect(buttons).toHaveLength(4);
            fireEvent.click(buttons[0]);
            expect(server.openResponse).toHaveBeenCalledWith({ workspace_id: 'workspace-1', submission_id: 'r1' });
        });

        it('has no checkbox column (there is nothing to do with a selection)', () => {
            renderTable();
            expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
        });

        it('lets a screen reader hear who answered and when (the responder cell is not hidden)', () => {
            renderTable();
            const email = screen.getByText('known.a@example.com');
            expect(email.closest('[aria-hidden="true"]')).toBeNull();
            expect(screen.getByText('Anonymous').closest('[aria-hidden="true"]')).toBeNull();
        });

        it('makes rows focusable and opens the response with Enter', () => {
            renderTable();
            const rows = screen.getAllByRole('row').filter((row) => row.id.startsWith('row-'));
            expect(rows).toHaveLength(4);
            rows.forEach((row) => expect(row).toHaveAttribute('tabindex', '0'));
            fireEvent.keyDown(rows[1], { key: 'Enter' });
            expect(server.openResponse).toHaveBeenCalledWith({ workspace_id: 'workspace-1', submission_id: 'r2' });
        });

        it('opens exactly once when the button inside the row is clicked (the click does not also hit the row)', () => {
            renderTable();
            const [button] = screen.getAllByRole('button', { name: 'Open response' });
            fireEvent.click(button);
            expect(server.openResponse).toHaveBeenCalledTimes(1);
            expect(server.openResponse).toHaveBeenCalledWith({ workspace_id: 'workspace-1', submission_id: 'r1' });
        });

        it('Enter on the "Open response" button is not also taken by the row: one open, from the button', () => {
            renderTable();
            const [button] = screen.getAllByRole('button', { name: 'Open response' });
            // the row only acts on keys pressed on the row itself
            fireEvent.keyDown(button, { key: 'Enter' });
            expect(server.openResponse).not.toHaveBeenCalled();
            // the browser then turns Enter on a button into a click
            fireEvent.click(button);
            expect(server.openResponse).toHaveBeenCalledTimes(1);
            expect(server.openResponse).toHaveBeenCalledWith({ workspace_id: 'workspace-1', submission_id: 'r1' });
        });

        it('gives the button column a header for screen readers', () => {
            renderTable();
            expect(screen.getByRole('columnheader', { name: 'Open' })).toBeInTheDocument();
        });
    });
});
