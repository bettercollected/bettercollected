import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The "server": one list of responses, filtered like the backend does for
// `dataOwnerIdentifier`. Every call the component makes is recorded.
type Item = { responseId: string; dataOwnerIdentifier: string | null; answers: any; createdAt: string };
const server: { items: Item[]; error: boolean; calls: any[]; refetchCalls: any[]; push: ReturnType<typeof vi.fn> } = { items: [], error: false, calls: [], refetchCalls: [], push: vi.fn() };

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
            if (server.error) return { data: undefined, isLoading: false, isFetching: false, isError: true, refetch };
            const term = arg.dataOwnerIdentifier;
            const items = term ? server.items.filter((item) => (item.dataOwnerIdentifier ?? '').includes(term)) : server.items;
            // pages of `arg.size` rows, like the backend
            const pages = Math.max(1, Math.ceil(items.length / arg.size));
            return { data: { items: items.slice((arg.page - 1) * arg.size, arg.page * arg.size), total: items.length, page: arg.page, pages, size: arg.size }, isLoading: false, isFetching: false, isError: false, refetch };
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

    describe('keyboard and screen reader basics', () => {
        it('labels the search box', () => {
            renderTable();
            expect(screen.getByRole('textbox', { name: 'Search responses by responder email' })).toBeInTheDocument();
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

        it('gives the button column a header for screen readers', () => {
            renderTable();
            expect(screen.getByRole('columnheader', { name: 'Open' })).toBeInTheDocument();
        });
    });
});
