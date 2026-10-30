import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The "server": one list of responses, filtered like the backend does for
// `dataOwnerIdentifier`. Every call the component makes is recorded.
type Item = { responseId: string; dataOwnerIdentifier: string | null; answers: any; createdAt: string };
// The hook answers like RTK Query does:
// - `data` is the last answer it got, whatever it asked for (kept while a new
//   page or search loads, and after an error); `currentData` is the answer
//   for this very argument (kept while the same argument is fetched again).
// - `pending` (or `pendingPages`): the server has not answered yet, so the hook
//   reports isFetching. isLoading is only true for a first load that never failed.
// - `stale`: like pending, with this as the earlier answer in `data`.
const server: {
    items: Item[];
    error: boolean;
    pending: boolean;
    pendingPages: Set<number>;
    stale: any;
    lastData: any;
    answered: Map<string, any>;
    calls: any[];
    refetchCalls: any[];
    push: ReturnType<typeof vi.fn>;
} = { items: [], error: false, pending: false, pendingPages: new Set(), stale: null, lastData: undefined, answered: new Map(), calls: [], refetchCalls: [], push: vi.fn() };

// a response opens on its own page: the table navigates to it
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: (url: string) => server.push(url) }), usePathname: () => '/', useSearchParams: () => new URLSearchParams() }));

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
            const key = JSON.stringify(arg);
            const cached = server.answered.get(key);
            if (server.stale || server.pending || server.pendingPages.has(arg.page)) return { data: server.stale ?? server.lastData, currentData: server.stale ? undefined : cached, isLoading: false, isFetching: true, isError: false, refetch };
            if (server.error) return { data: server.lastData, currentData: cached, isLoading: false, isFetching: false, isError: true, refetch };
            const term = arg.dataOwnerIdentifier;
            const items = term ? server.items.filter((item) => (item.dataOwnerIdentifier ?? '').includes(term)) : server.items;
            // pages of `arg.size` rows, like the backend
            const pages = Math.max(1, Math.ceil(items.length / arg.size));
            const data = { items: items.slice((arg.page - 1) * arg.size, arg.page * arg.size), total: items.length, page: arg.page, pages, size: arg.size };
            server.answered.set(key, data);
            server.lastData = data;
            return { data, currentData: data, isLoading: false, isFetching: false, isError: false, refetch };
        },
        useLazyExportFormSubmissionsQuery: () => [vi.fn(), { isLoading: false }],
        useLazyGetWorkspaceFormVersionQuery: () => [vi.fn()],
        useGetWorkspacePermissionsQuery: () => ({ data: { permissions: [] }, isLoading: false, isError: false })
    };
});

import { FieldTypes } from '@app/models/dtos/form';
import I18nProvider from '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { forgetResponseList, rememberedNeighbours } from '@app/utils/response-list-memory';

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
// the cache key of another page of the list last asked for
const pageKey = (page: number) => JSON.stringify({ ...lastQuery(), page });

describe('responses table: search and honest states', () => {
    beforeEach(() => {
        // jsdom has no matchMedia; react-data-table-component asks for it
        window.matchMedia = ((query: string) => ({ matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false, onchange: null })) as any;
        vi.useFakeTimers();
        server.error = false;
        server.pending = false;
        server.pendingPages = new Set();
        server.stale = null;
        server.lastData = undefined;
        server.answered = new Map();
        server.calls = [];
        server.refetchCalls = [];
        server.push = vi.fn();
        // the list memory outlives a render (as it outlives a page): every test starts without one
        forgetResponseList();
        server.items = [item('r1', 'known.a@example.com', 'blue'), item('r2', 'known.b@example.com', 'green'), item('r3', 'other@example.com', 'red'), item('r4', null, 'pink')];
        store.dispatch(setWorkspace({ id: 'workspace-1', workspaceName: 'acme' } as any));
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

    describe('back from a response', () => {
        it('opens again on the page it was left on', () => {
            server.items = Array.from({ length: 40 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { unmount } = renderTable();
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(lastQuery().page).toBe(2);
            // the response's page replaces the list, then "Responses" (or the browser's Back) brings it back
            unmount();
            server.calls = [];
            renderTable();
            expect(server.calls.filter((call) => !call.options?.skip)[0].arg).toMatchObject({ page: 2 });
        });

        it('goes to the last page with responses when the page it was left on is now empty (its only response was deleted)', () => {
            // 16 responses, 15 a page: page 2 holds one
            server.items = Array.from({ length: 16 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { unmount } = renderTable();
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(screen.getByText('person15@example.com')).toBeInTheDocument();
            // its page is opened and the response deleted; "Responses" brings the list back
            unmount();
            server.items = server.items.slice(0, 15);
            server.calls = [];
            renderTable();
            expect(lastQuery()).toMatchObject({ page: 1 });
            expect(screen.getByText('person0@example.com')).toBeInTheDocument();
            expect(screen.queryByText('No responses yet')).toBeNull();
            // and the memory keeps the page it is on now
            unmount();
            server.calls = [];
            renderTable();
            expect(server.calls.filter((call) => !call.options?.skip)[0].arg).toMatchObject({ page: 1 });
        });

        it('steps back to the last page that has responses when several pages emptied', () => {
            server.items = Array.from({ length: 46 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { unmount } = renderTable();
            fireEvent.click(screen.getByLabelText(/next/i));
            fireEvent.click(screen.getByLabelText(/next/i));
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(lastQuery().page).toBe(4);
            unmount();
            // someone else deleted 30 of them
            server.items = server.items.slice(0, 16);
            server.calls = [];
            renderTable();
            expect(lastQuery()).toMatchObject({ page: 2 });
            expect(screen.getByText('person15@example.com')).toBeInTheDocument();
        });

        it("never steps back on the previous page's answer while the page asked for still loads", () => {
            server.items = Array.from({ length: 46 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            renderTable();
            fireEvent.click(screen.getByLabelText(/next/i));
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(lastQuery().page).toBe(3);
            // page 4 is asked for; until it answers, the hook still holds an empty earlier answer
            server.stale = { items: [], total: 16, page: 3, pages: 2, size: 15 };
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(lastQuery().page).toBe(4);
        });

        it('says "No responses yet" on page 1 when every response is gone', () => {
            server.items = Array.from({ length: 16 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { unmount } = renderTable();
            fireEvent.click(screen.getByLabelText(/next/i));
            unmount();
            server.items = [];
            server.calls = [];
            renderTable();
            expect(lastQuery()).toMatchObject({ page: 1 });
            expect(screen.getByText('No responses yet')).toBeInTheDocument();
        });

        it('opens again with the search it was left with, shown in the search box', () => {
            const { unmount } = renderTable();
            search('known');
            unmount();
            server.calls = [];
            renderTable();
            expect(server.calls.filter((call) => !call.options?.skip)[0].arg).toMatchObject({ dataOwnerIdentifier: 'known', page: 1 });
            expect((screen.getByPlaceholderText('Search by responder email') as HTMLInputElement).value).toBe('known');
            expect(screen.queryByText('other@example.com')).toBeNull();
        });

        it('starts on page 1 with no search for another form', () => {
            const { unmount } = renderTable();
            search('known');
            unmount();
            store.dispatch(setForm({ ...store.getState().form, formId: 'form-2' } as any));
            server.calls = [];
            renderTable();
            expect(lastQuery()).toMatchObject({ formId: 'form-2', page: 1 });
            expect(lastQuery()).not.toHaveProperty('dataOwnerIdentifier');
        });

        it('keeps the deletion requests list out of it', () => {
            const { unmount } = renderTable();
            search('known');
            unmount();
            store.dispatch(setForm({ ...store.getState().form, deletionRequests: 2 } as any));
            server.calls = [];
            renderTable({ requestForDeletion: true, isSubmission: false });
            expect(lastQuery()).not.toHaveProperty('dataOwnerIdentifier');
        });
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
            // the full list's earlier answer is no longer cached (RTK Query drops unused answers after a minute)
            server.answered.clear();
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

        it('a refetch of the same empty list (tab focus) keeps "No responses yet" on screen, without the loader', () => {
            server.items = [];
            const { rerender } = renderTable();
            expect(screen.getByText('No responses yet')).toBeInTheDocument();
            // the same list is asked for again: its answer stays in currentData
            server.pending = true;
            rerender(tree());
            expect(screen.getByText('No responses yet')).toBeInTheDocument();
            expect(screen.queryByRole('status', { name: 'Loading responses' })).toBeNull();
        });

        it('a refetch of the same no-match search keeps "No responses match" on screen, without the loader', () => {
            const { rerender } = renderTable();
            search('nobody');
            expect(screen.getByText('No responses match')).toBeInTheDocument();
            server.pending = true;
            rerender(tree());
            expect(screen.getByText('No responses match')).toBeInTheDocument();
            expect(screen.queryByRole('status', { name: 'Loading responses' })).toBeNull();
        });

        it('a refetch of the same deletion requests keeps "No deletion requests" on screen', () => {
            server.items = [];
            const { rerender } = renderTable({ requestForDeletion: true, isSubmission: false });
            expect(screen.getByText('No deletion requests')).toBeInTheDocument();
            server.pending = true;
            rerender(tree({ requestForDeletion: true, isSubmission: false }));
            expect(screen.getByText('No deletion requests')).toBeInTheDocument();
            expect(screen.queryByRole('status', { name: 'Loading responses' })).toBeNull();
        });

        it("Retry shows the loader until the server answers, not the previous page's rows the hook still holds", () => {
            server.items = Array.from({ length: 16 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { rerender } = renderTable();
            server.error = true;
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(screen.getByText('Could not load responses')).toBeInTheDocument();
            server.error = false;
            server.pending = true;
            fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
            expect(screen.getByRole('status', { name: 'Loading responses' })).toBeInTheDocument();
            expect(screen.queryByText('person0@example.com')).toBeNull();
            // the server answers: page 2's row, and the loader is gone
            server.pending = false;
            rerender(tree());
            expect(screen.getByText('person15@example.com')).toBeInTheDocument();
            expect(screen.queryByRole('status', { name: 'Loading responses' })).toBeNull();
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
            // the last row on page 3 is deleted; page 2's earlier answer is no longer cached
            server.items = many(30);
            server.answered.delete(pageKey(2));
            server.pendingPages = new Set([2]);
            rerender(tree());
            expect(lastQuery().page).toBe(2);
            // while page 2 is asked for, the hook still holds the empty page 3: the loader, never "No responses yet"
            expect(screen.getByRole('status', { name: 'Loading responses' })).toBeInTheDocument();
            expect(screen.queryByText('No responses yet')).toBeNull();
            // page 2 answers
            server.pendingPages = new Set();
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

        it('a failed refetch of a page whose last answer was empty stays an error instead of stepping back', () => {
            server.items = many(16);
            renderTable();
            // the cache still holds an empty answer for page 2 (RTK Query keeps it when its refetch fails)
            server.answered.set(pageKey(2), { items: [], total: 16, page: 2, pages: 2, size: 15 });
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

        it('opens a response from a real link named "Open response", to its own page', () => {
            renderTable();
            const links = screen.getAllByRole('link', { name: 'Open response' });
            expect(links).toHaveLength(4);
            // a real href: cmd/ctrl-click and "open in new tab" work
            expect(links[0]).toHaveAttribute('href', '/acme/dashboard/forms/form-1/responses/r1');
            expect(links[3]).toHaveAttribute('href', '/acme/dashboard/forms/form-1/responses/r4');
        });

        it('opens the page when a row is clicked, and in a new tab with ctrl/cmd', () => {
            renderTable();
            // the table reacts to a click on a cell of the row
            const cell = (text: string) => screen.getByText(text).closest('[data-tag="allowRowEvents"]') as HTMLElement;
            fireEvent.click(cell('other@example.com'));
            expect(server.push).toHaveBeenCalledWith('/acme/dashboard/forms/form-1/responses/r3');
            const open = vi.spyOn(window, 'open').mockImplementation(() => null);
            fireEvent.click(cell('known.a@example.com'), { ctrlKey: true });
            expect(open).toHaveBeenCalledWith('/acme/dashboard/forms/form-1/responses/r1', '_blank', 'noopener');
            expect(server.push).toHaveBeenCalledTimes(1);
            open.mockRestore();
        });

        it('remembers previous/next only from the answer for the page shown, never the previous rows while the next page loads', () => {
            server.items = Array.from({ length: 31 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { rerender } = renderTable();
            expect(rememberedNeighbours('workspace-1', 'form-1', 'p14')).toMatchObject({ previousId: 'p13', position: 15 });
            // page 2 is asked for: the table still shows page 1's rows, marked busy
            server.pending = true;
            fireEvent.click(screen.getByLabelText(/next/i));
            expect(lastQuery().page).toBe(2);
            expect(screen.getByText('person0@example.com').closest('[aria-busy="true"]')).not.toBeNull();
            expect(rememberedNeighbours('workspace-1', 'form-1', 'p14').nextId).toBeUndefined();
            // and it fails: page 1's ids are still not page 2
            server.pending = false;
            server.error = true;
            rerender(tree());
            expect(screen.getByText('Could not load responses')).toBeInTheDocument();
            expect(rememberedNeighbours('workspace-1', 'form-1', 'p14').nextId).toBeUndefined();
            // Retry answers: now page 2 is known
            server.error = false;
            fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
            expect(screen.getByText('person15@example.com')).toBeInTheDocument();
            expect(rememberedNeighbours('workspace-1', 'form-1', 'p14')).toMatchObject({ nextId: 'p15' });
            expect(rememberedNeighbours('workspace-1', 'form-1', 'p15')).toMatchObject({ previousId: 'p14', position: 16, total: 31 });
        });

        it('remembers the order on screen (ids only) for previous/next on a response page', () => {
            forgetResponseList();
            renderTable();
            expect(rememberedNeighbours('workspace-1', 'form-1', 'r2')).toMatchObject({ previousId: 'r1', nextId: 'r3', position: 2, total: 4 });
            // another workspace's form with the same id is another list
            expect(rememberedNeighbours('workspace-2', 'form-1', 'r2')).toEqual({});
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
            expect(server.push).toHaveBeenCalledWith('/acme/dashboard/forms/form-1/responses/r2');
        });

        it('goes to the page once when the link inside the row is clicked (the click does not also hit the row)', () => {
            renderTable();
            const [link] = screen.getAllByRole('link', { name: 'Open response' });
            // the link navigates by itself; the row's own handler must not push a second time
            link.addEventListener('click', (event) => event.preventDefault());
            fireEvent.click(link);
            expect(server.push).not.toHaveBeenCalled();
        });

        it('Enter on the "Open response" link is not also taken by the row: the link opens the page, the row does not push it again', () => {
            renderTable();
            const [link] = screen.getAllByRole('link', { name: 'Open response' });
            // the row only acts on keys pressed on the row itself; the browser follows the link
            fireEvent.keyDown(link, { key: 'Enter' });
            expect(server.push).not.toHaveBeenCalled();
            // the same key on the row opens it once
            fireEvent.keyDown(link.closest('[role="row"]') as HTMLElement, { key: 'Enter' });
            expect(server.push).toHaveBeenCalledTimes(1);
            expect(server.push).toHaveBeenCalledWith('/acme/dashboard/forms/form-1/responses/r1');
        });

        it('gives the button column a header for screen readers', () => {
            renderTable();
            expect(screen.getByRole('columnheader', { name: 'Open' })).toBeInTheDocument();
        });
    });
});
