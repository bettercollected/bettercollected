import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
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
    errorBody: any;
    cappedAt: number | null;
    pending: boolean;
    pendingPages: Set<number>;
    stale: any;
    lastData: any;
    answered: Map<string, any>;
    calls: any[];
    refetchCalls: any[];
    push: ReturnType<typeof vi.fn>;
} = { items: [], error: false, errorBody: undefined, cappedAt: null, pending: false, pendingPages: new Set(), stale: null, lastData: undefined, answered: new Map(), calls: [], refetchCalls: [], push: vi.fn() };

// The URL: the list keeps page, size, sort and filters in it, so the router
// and the search params are one small store, as in the app.
const LIST_PATH = '/acme/dashboard/forms/form-1/responses';
const nav = { search: '', listeners: new Set<() => void>(), listPushes: [] as string[], replaces: [] as string[] };
const goTo = (url: string, record: string[]) => {
    record.push(url);
    nav.search = url.includes('?') ? url.split('?')[1] : '';
    nav.listeners.forEach((listener) => listener());
};
const router = {
    // a response opens on its own page: the table navigates to it; the list's own URL changes are the store's
    push: (url: string) => (url.split('?')[0] === LIST_PATH ? goTo(url, nav.listPushes) : server.push(url)),
    replace: (url: string) => (url.split('?')[0] === LIST_PATH ? goTo(url, nav.replaces) : server.push(url))
};
vi.mock('next/navigation', () => ({
    useRouter: () => router,
    usePathname: () => LIST_PATH,
    useSearchParams: () => {
        const [, force] = React.useState(0);
        React.useEffect(() => {
            const listener = () => force((tick) => tick + 1);
            nav.listeners.add(listener);
            return () => {
                nav.listeners.delete(listener);
            };
        }, []);
        return React.useMemo(() => new URLSearchParams(nav.search), [nav.search]);
    }
}));
// a pager link follows its href through the router, as Next's does
vi.mock('next/link', () => ({
    default: ({ href, children, onClick, scroll, prefetch, ...rest }: any) => (
        <a
            href={href}
            {...rest}
            onClick={(event) => {
                onClick?.(event);
                if (event.defaultPrevented || event.ctrlKey || event.metaKey) return;
                event.preventDefault();
                router.push(href);
            }}
        >
            {children}
        </a>
    )
}));

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
            if (server.error) return { data: server.lastData, currentData: cached, isLoading: false, isFetching: false, isError: true, error: server.errorBody, refetch };
            let items = server.items;
            if (arg.dataOwnerIdentifier) items = items.filter((item) => (item.dataOwnerIdentifier ?? '').includes(arg.dataOwnerIdentifier));
            if (arg.respondent) items = items.filter((item) => (arg.respondent === 'anonymous' ? !item.dataOwnerIdentifier : !!item.dataOwnerIdentifier));
            // pages of `arg.size` rows, like the backend; the keyset list also says whether the total is exact and what follows
            const pages = Math.max(1, Math.ceil(items.length / arg.size));
            const total = server.cappedAt !== null ? Math.min(items.length, server.cappedAt) : items.length;
            const rows = items.slice((arg.page - 1) * arg.size, arg.page * arg.size);
            const data = {
                items: rows,
                total,
                page: arg.page,
                pages,
                size: arg.size,
                ...(arg.paging === 'keyset' ? { totalExact: server.cappedAt === null || items.length <= server.cappedAt, hasNext: arg.page * arg.size < items.length, cursor: rows.length ? `cursor-${arg.page}` : undefined } : {})
            };
            server.answered.set(key, data);
            server.lastData = data;
            return { data, currentData: data, isLoading: false, isFetching: false, isError: false, refetch };
        },
        // the export button follows its own tests (response-export-control.test.tsx)
        useGetResponseExportsQuery: () => ({ data: [], refetch: vi.fn() }),
        useGetResponseExportQuery: () => ({ data: undefined, refetch: vi.fn() }),
        useStartResponseExportMutation: () => [vi.fn()],
        useDownloadResponseExportMutation: () => [vi.fn()],
        useDiscardResponseExportMutation: () => [vi.fn()],
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
import { axeViolations } from '@app/test/axe';
import commonEn from '../../../public/locales/en/common.json';
import commonNl from '../../../public/locales/nl/common.json';

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
// a list opened by a link (not by Back) has no parameters in its address
const renderTable = (props: any = {}) => {
    nav.search = '';
    return render(tree(props));
};
// the pager's links: both pagers (above and below the table) say the same
const pagerLink = (name: string | RegExp) => screen.getAllByRole('link', { name })[0];
const next = () => fireEvent.click(pagerLink('Next page'));
const urlParams = () => new URLSearchParams(nav.search);
// the filters sit behind the Filters button (what is in force shows as chips beside it)
const openFilters = () => {
    const toggle = screen.getByRole('button', { name: /^Filters(,|$)/ });
    if (toggle.getAttribute('aria-expanded') !== 'true') fireEvent.click(toggle);
};

const search = (text: string) => {
    fireEvent.change(screen.getByPlaceholderText('Search by responder email'), { target: { value: text } });
    // SearchInput debounces by 500 ms
    act(() => {
        vi.advanceTimersByTime(600);
    });
};

const lastQuery = () => server.calls.filter((call) => !call.options?.skip).at(-1)?.arg;
// RTK Query drops the answers nobody uses any more: forget the ones for a page
const forgetAnswers = (page: number) => [...server.answered].forEach(([key, answer]) => answer.page === page && server.answered.delete(key));

describe('responses table: search and honest states', () => {
    beforeEach(() => {
        // jsdom has no matchMedia; react-data-table-component asks for it
        window.matchMedia = ((query: string) => ({ matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false, onchange: null })) as any;
        vi.useFakeTimers();
        server.error = false;
        server.errorBody = undefined;
        server.cappedAt = null;
        nav.listPushes = [];
        nav.replaces = [];
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
        next();
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
        next();
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
        next();
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
            next();
            expect(lastQuery().page).toBe(2);
            // the response's page replaces the list, then "Responses" (or the browser's Back) brings it back
            unmount();
            server.calls = [];
            renderTable();
            expect(server.calls.filter((call) => !call.options?.skip)[0].arg).toMatchObject({ page: 2 });
        });

        it('goes to the last page with responses when the page it was left on is now empty (its only response was deleted)', () => {
            // 26 responses, 25 a page: page 2 holds one
            server.items = Array.from({ length: 26 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { unmount } = renderTable();
            next();
            expect(screen.getByText('person25@example.com')).toBeInTheDocument();
            // its page is opened and the response deleted; "Responses" brings the list back
            unmount();
            server.items = server.items.slice(0, 25);
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
            server.items = Array.from({ length: 100 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { unmount } = renderTable();
            next();
            next();
            next();
            expect(lastQuery().page).toBe(4);
            unmount();
            // someone else deleted 30 of them
            server.items = server.items.slice(0, 26);
            server.calls = [];
            renderTable();
            expect(lastQuery()).toMatchObject({ page: 2 });
            expect(screen.getByText('person25@example.com')).toBeInTheDocument();
        });

        it("never steps back on the previous page's answer while the page asked for still loads", () => {
            server.items = Array.from({ length: 100 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            renderTable();
            next();
            next();
            expect(lastQuery().page).toBe(3);
            // page 4 is asked for; until it answers, the hook still holds an empty earlier answer
            server.stale = { items: [], total: 26, page: 3, pages: 2, size: 25 };
            next();
            expect(lastQuery().page).toBe(4);
        });

        it('says "No responses yet" on page 1 when every response is gone', () => {
            server.items = Array.from({ length: 26 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { unmount } = renderTable();
            next();
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
            server.items = Array.from({ length: 26 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { rerender } = renderTable();
            server.error = true;
            next();
            expect(screen.getByText('Could not load responses')).toBeInTheDocument();
            server.error = false;
            server.pending = true;
            fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
            expect(screen.getByRole('status', { name: 'Loading responses' })).toBeInTheDocument();
            expect(screen.queryByText('person0@example.com')).toBeNull();
            // the server answers: page 2's row, and the loader is gone
            server.pending = false;
            rerender(tree());
            expect(screen.getByText('person25@example.com')).toBeInTheDocument();
            expect(screen.queryByRole('status', { name: 'Loading responses' })).toBeNull();
        });
    });

    describe('a later page that empties', () => {
        const many = (count: number) => Array.from({ length: count }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));

        it('steps back to the last page that still has rows, keeping the pagination', () => {
            // 51 rows: three pages of 25, 25 and 1
            server.items = many(51);
            const { rerender } = renderTable();
            next();
            next();
            expect(lastQuery().page).toBe(3);
            expect(screen.getByText('person50@example.com')).toBeInTheDocument();
            // the last row on page 3 is deleted; page 2's earlier answer is no longer cached
            server.items = many(50);
            forgetAnswers(2);
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
            expect(screen.getByText('person25@example.com')).toBeInTheDocument();
            expect(pagerLink('Previous page')).toHaveAttribute('href');
            expect(screen.queryByText('No responses yet')).toBeNull();
        });

        it('says "No responses yet" only once the whole form has none', () => {
            server.items = many(26);
            const { rerender } = renderTable();
            next();
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
            server.items = many(26);
            renderTable();
            server.error = true;
            next();
            expect(screen.getByText('Could not load responses')).toBeInTheDocument();
            expect(lastQuery().page).toBe(2);
        });

        it('a failed refetch of a page whose last answer was empty stays an error instead of stepping back', () => {
            server.items = many(26);
            renderTable();
            // the cache still holds an empty answer for page 2 (RTK Query keeps it when its refetch fails)
            server.answered.set(JSON.stringify({ ...lastQuery(), page: 2, cursor: 'cursor-1' }), { items: [], total: 26, page: 2, pages: 2, size: 25 });
            server.error = true;
            next();
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
        it('limits the search to the 320 characters the server takes', () => {
            renderTable();
            expect(screen.getByPlaceholderText('Search by responder email')).toHaveAttribute('maxlength', '320');
        });

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
            expect(rememberedNeighbours('workspace-1', 'form-1', 'p24')).toMatchObject({ previousId: 'p23', position: 25 });
            // page 2 is asked for: the table still shows page 1's rows, marked busy
            server.pending = true;
            next();
            expect(lastQuery().page).toBe(2);
            expect(screen.getByText('person0@example.com').closest('[aria-busy="true"]')).not.toBeNull();
            expect(rememberedNeighbours('workspace-1', 'form-1', 'p24').nextId).toBeUndefined();
            // and it fails: page 1's ids are still not page 2
            server.pending = false;
            server.error = true;
            rerender(tree());
            expect(screen.getByText('Could not load responses')).toBeInTheDocument();
            expect(rememberedNeighbours('workspace-1', 'form-1', 'p24').nextId).toBeUndefined();
            // Retry answers: now page 2 is known
            server.error = false;
            fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
            expect(screen.getByText('person25@example.com')).toBeInTheDocument();
            expect(rememberedNeighbours('workspace-1', 'form-1', 'p24')).toMatchObject({ nextId: 'p25' });
            expect(rememberedNeighbours('workspace-1', 'form-1', 'p25')).toMatchObject({ previousId: 'p24', position: 26, total: 31 });
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
            expect(screen.getAllByText('Anonymous').find((element) => element.tagName !== 'OPTION')!.closest('[aria-hidden="true"]')).toBeNull();
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

    describe('filters, sort and paging in the URL', () => {
        const many = (count: number) => Array.from({ length: count }, (_, index) => item(`p${index}`, index % 2 ? `person${index}@example.com` : null, 'blue'));
        const openAt = (query: string) => {
            nav.search = query;
            return render(tree());
        };
        const select = (label: string, value: string) => {
            if (label !== 'Sort by') openFilters();
            fireEvent.change(screen.getByLabelText(label), { target: { value } });
        };

        it('asks the server for what the URL says', () => {
            server.items = many(120);
            openAt('page=2&size=50&sort=oldest&from=2026-01-05&to=2026-01-09&status=pending&who=known&version=1&cursor=tok.en');
            const arg = lastQuery();
            expect(arg).toMatchObject({ paging: 'keyset', page: 2, size: 50, sort_by: 'created_at', sort_order: 'ASCENDING', status: 'pending', respondent: 'known', formVersion: 1, cursor: 'tok.en' });
            expect(arg.submittedFrom).toBe(new Date(2026, 0, 5).toISOString());
            expect(arg.submittedTo).toBe(new Date(2026, 0, 10).toISOString());
        });

        it('shows the state in the controls', () => {
            openAt('sort=version-high&from=2026-01-05&to=2026-01-09&status=none&who=anonymous&version=1');
            openFilters();
            expect(screen.getByLabelText('Submitted from')).toHaveValue('2026-01-05');
            expect(screen.getByLabelText('Submitted until')).toHaveValue('2026-01-09');
            expect(screen.getByLabelText('Deletion request')).toHaveValue('none');
            expect(screen.getByLabelText('Responder')).toHaveValue('anonymous');
            expect(screen.getByLabelText('Form version')).toHaveValue('1');
            expect(screen.getByLabelText('Sort by')).toHaveValue('version-high');
        });

        it('opens the list, not an error, for a hand-edited or stale URL', () => {
            openAt('page=banana&size=7&sort=drop&from=2026-02-31&cursor=%27%3B--');
            expect(lastQuery()).toMatchObject({ page: 1, size: 25, sort_by: 'created_at', sort_order: 'DESCENDING' });
            expect(lastQuery().cursor).toBeUndefined();
            expect(screen.getByText('known.a@example.com')).toBeInTheDocument();
        });

        it('puts a changed filter in the URL, from page 1 and without the old cursor', () => {
            server.items = many(120);
            openAt('page=3&cursor=cursor-2');
            select('Responder', 'known');
            expect(nav.listPushes.at(-1)).toBe(`${LIST_PATH}?who=known`);
            expect(lastQuery()).toMatchObject({ page: 1, respondent: 'known' });
            expect(lastQuery().cursor).toBeUndefined();
            select('Sort by', 'oldest');
            expect(urlParams().get('sort')).toBe('oldest');
            expect(urlParams().get('who')).toBe('known');
        });

        it('keeps each filter in the URL and clears them all with one button', () => {
            openAt('page=2&sort=oldest');
            openFilters();
            fireEvent.change(screen.getByLabelText('Submitted from'), { target: { value: '2026-03-01' } });
            select('Deletion request', 'pending');
            select('Form version', '1');
            expect(urlParams().get('from')).toBe('2026-03-01');
            expect(urlParams().get('status')).toBe('pending');
            expect(urlParams().get('version')).toBe('1');
            fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
            // the sort stays: it is not a filter
            expect(nav.search).toBe('sort=oldest');
            expect(screen.queryByRole('button', { name: 'Clear filters' })).toBeNull();
        });

        it('does not let the end date go before the start date', () => {
            openAt('from=2026-03-10');
            openFilters();
            expect(screen.getByLabelText('Submitted until')).toHaveAttribute('min', '2026-03-10');
            expect(screen.getByLabelText('Submitted from')).not.toHaveAttribute('min');
        });

        it('follows Back and Forward: the list is whatever the URL says', () => {
            server.items = many(120);
            renderTable();
            select('Responder', 'known');
            next();
            expect(lastQuery()).toMatchObject({ page: 2, respondent: 'known' });
            // Back, as the browser does: the URL changes under the page
            act(() => goTo(`${LIST_PATH}?who=known`, []));
            expect(lastQuery()).toMatchObject({ page: 1, respondent: 'known' });
            act(() => goTo(LIST_PATH, []));
            expect(lastQuery().respondent).toBeUndefined();
            expect(screen.getByLabelText('Responder')).toHaveValue('');
        });

        it('never puts the responder search in the URL, and keeps it with the filters', () => {
            renderTable();
            search('known');
            select('Sort by', 'oldest');
            expect(nav.search).toBe('sort=oldest');
            expect(nav.search).not.toContain('known');
            expect(lastQuery()).toMatchObject({ dataOwnerIdentifier: 'known', sort_order: 'ASCENDING' });
        });

        it('a new search starts on page 1 and drops the cursor made for the old search', () => {
            server.items = many(120);
            openAt('page=2&cursor=cursor-1');
            search('person');
            expect(nav.search).toBe('');
            expect(lastQuery()).toMatchObject({ page: 1, dataOwnerIdentifier: 'person' });
            expect(lastQuery().cursor).toBeUndefined();
        });

        it('changes the page size from the pager and starts again on page 1', () => {
            server.items = many(120);
            openAt('page=3&cursor=cursor-2');
            fireEvent.change(screen.getByLabelText('Rows per page'), { target: { value: '100' } });
            expect(nav.search).toBe('size=100');
            expect(lastQuery()).toMatchObject({ page: 1, size: 100 });
        });

        it('offers the three page sizes', () => {
            renderTable();
            const sizes = Array.from((screen.getByLabelText('Rows per page') as HTMLSelectElement).options).map((option) => option.value);
            expect(sizes).toEqual(['25', '50', '100']);
        });

        it('offers the form versions that exist, the current one marked', () => {
            store.dispatch(setForm({ ...store.getState().form, version: 3 } as any));
            renderTable();
            openFilters();
            const options = Array.from((screen.getByLabelText('Form version') as HTMLSelectElement).options).map((option) => option.textContent);
            expect(options).toEqual(['All versions', 'Version 3 (current)', 'Version 2', 'Version 1']);
        });

        it('restores the filters, sort and page of the list when it is opened again by a link', () => {
            server.items = many(120);
            const { unmount } = renderTable();
            select('Responder', 'known');
            next();
            expect(nav.search).toContain('page=2');
            unmount();
            server.calls = [];
            renderTable();
            // the link had no parameters: the remembered ones are put back (once)
            expect(nav.replaces.at(-1)).toContain('who=known');
            expect(lastQuery()).toMatchObject({ page: 2, respondent: 'known' });
        });
    });

    describe('the pager', () => {
        const many = (count: number) => Array.from({ length: count }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
        const hrefOf = (name: string | RegExp) => new URL(pagerLink(name).getAttribute('href')!, 'http://x').searchParams;

        it('is a labelled navigation of links with the current page marked', () => {
            server.items = many(300);
            nav.search = 'page=5&cursor=cursor-4';
            render(tree());
            const pagers = screen.getAllByRole('navigation');
            expect(pagers.map((pager) => pager.getAttribute('aria-label'))).toEqual(['Pages of responses (above the table)', 'Pages of responses (below the table)']);
            const bottom = within(pagers[1]);
            expect(bottom.getByText('5', { selector: '[aria-current="page"]' })).toBeInTheDocument();
            expect(bottom.getAllByRole('link').map((link) => link.getAttribute('aria-label'))).toEqual(['First page', 'Previous page', 'Page 3', 'Page 4', 'Page 6', 'Page 7', 'Next page', 'Last page']);
        });

        it('sends the shown page\'s cursor with the nearby pages, and none with the first and the last', () => {
            server.items = many(300);
            renderTable();
            next(); // page 2, cursor-1 (the page before)
            expect(urlParams().get('page')).toBe('2');
            expect(urlParams().get('cursor')).toBe('cursor-1');
            // now standing on page 2: its own cursor is what the links carry
            expect(hrefOf('Next page').get('page')).toBe('3');
            expect(hrefOf('Next page').get('cursor')).toBe('cursor-2');
            expect(hrefOf('Previous page').get('page')).toBeNull(); // page 1: the default
            expect(hrefOf('Page 4').get('cursor')).toBe('cursor-2');
            expect(hrefOf('First page').has('cursor')).toBe(false);
            expect(hrefOf('Last page').get('page')).toBe('12');
            expect(hrefOf('Last page').has('cursor')).toBe(false);
            // the filters travel with every link
        });

        it('keeps the filters and the sort in every link', () => {
            server.items = many(300);
            nav.search = 'sort=oldest&who=known&size=50';
            render(tree());
            const params = hrefOf('Next page');
            expect(params.get('sort')).toBe('oldest');
            expect(params.get('who')).toBe('known');
            expect(params.get('size')).toBe('50');
        });

        it('has no previous or first link on page 1 and no next or last on the last page', () => {
            server.items = many(60);
            renderTable();
            const disabled = (name: string) => screen.getAllByLabelText(name).every((element) => element.getAttribute('aria-disabled') === 'true' && !element.hasAttribute('href'));
            expect(disabled('First page')).toBe(true);
            expect(disabled('Previous page')).toBe(true);
            next();
            next();
            expect(disabled('Next page')).toBe(true);
            expect(disabled('Last page')).toBe(true);
            expect(pagerLink('Previous page')).toHaveAttribute('href');
        });

        it('reaches the pages by Tab and Enter (real links, in document order)', () => {
            server.items = many(300);
            renderTable();
            const links = screen.getAllByRole('link', { name: /page/i }).filter((link) => link.hasAttribute('href'));
            // a link is a tab stop by itself: no negative tabindex
            links.forEach((link) => expect(link.getAttribute('tabindex')).not.toBe('-1'));
            const nextLink = pagerLink('Next page');
            nextLink.focus();
            expect(document.activeElement).toBe(nextLink);
        });

        it('says that the total is a cap, and offers no last page', () => {
            server.items = many(300);
            server.cappedAt = 100;
            renderTable();
            expect(screen.getByRole('status')).toHaveTextContent('Showing 1–25 of 100+');
            const last = screen.getAllByLabelText(/Last page/)[0];
            expect(last).toHaveAttribute('aria-disabled', 'true');
            expect(last.getAttribute('aria-label')).toContain('not available');
            // the other end is a sort away; next still works past the cap
            expect(pagerLink('Next page')).toHaveAttribute('href');
        });

        it('says where it is for a list that fits on one page', () => {
            renderTable();
            expect(screen.getByRole('status')).toHaveTextContent('Showing 1–4 of 4');
        });
    });

    describe('the results count and focus', () => {
        const many = (count: number) => Array.from({ length: count }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));

        it('is a polite, atomic live region that says which rows are shown', () => {
            server.items = many(60);
            renderTable();
            const region = screen.getByRole('status');
            expect(region).toHaveAttribute('aria-live', 'polite');
            expect(region).toHaveAttribute('aria-atomic', 'true');
            expect(region).toHaveTextContent('Showing 1–25 of 60');
            next();
            expect(region).toHaveTextContent('Showing 26–50 of 60');
            next();
            expect(region).toHaveTextContent('Showing 51–60 of 60');
        });

        it('groups thousands in the count', () => {
            server.items = many(2500);
            renderTable();
            expect(screen.getByRole('status')).toHaveTextContent('Showing 1–25 of 2,500');
        });

        it('moves focus to the results once the page followed from the pager has arrived', () => {
            server.items = many(60);
            renderTable();
            const link = pagerLink('Next page');
            link.focus();
            fireEvent.click(link);
            expect(lastQuery().page).toBe(2);
            expect(document.activeElement).toBe(screen.getByRole('region', { name: 'Responses' }));
        });

        it('leaves focus alone for a filter or a search', () => {
            server.items = many(60);
            renderTable();
            const sort = screen.getByLabelText('Sort by');
            sort.focus();
            fireEvent.change(sort, { target: { value: 'oldest' } });
            expect(document.activeElement).toBe(sort);
        });

        it('waits for the new page before moving focus', () => {
            server.items = many(60);
            renderTable();
            server.pending = true;
            fireEvent.click(pagerLink('Next page'));
            expect(document.activeElement).not.toBe(screen.getByRole('region', { name: 'Responses' }));
        });
    });

    describe('when nothing matches or the server refuses', () => {
        it('says that no response matches the filters, with a way out, never "No responses yet"', () => {
            server.items = [item('r1', 'a@example.com', 'blue'), item('r2', 'b@example.com', 'blue')];
            renderTable();
            openFilters();
            fireEvent.change(screen.getByLabelText('Responder'), { target: { value: 'anonymous' } });
            expect(screen.getByText('No responses match these filters')).toBeInTheDocument();
            expect(screen.queryByText('No responses yet')).toBeNull();
            // the filters stay on screen so they can be changed
            expect(screen.getByLabelText('Responder')).toHaveValue('anonymous');
            fireEvent.click(screen.getAllByRole('button', { name: 'Clear filters' }).at(-1)!);
            expect(screen.getByText('a@example.com')).toBeInTheDocument();
        });

        it('drops a cursor the server refuses and asks again without it', () => {
            server.items = Array.from({ length: 60 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            nav.search = 'page=2&cursor=old.cursor';
            server.error = true;
            server.errorBody = { status: 400, data: { code: 'invalid_cursor' } };
            const { rerender } = render(tree());
            expect(nav.replaces.at(-1)).toBe(`${LIST_PATH}?page=2`);
            server.error = false;
            rerender(tree());
            expect(lastQuery()).toMatchObject({ page: 2 });
            expect(lastQuery().cursor).toBeUndefined();
            expect(screen.getByText('person25@example.com')).toBeInTheDocument();
        });

        it('says when a page is too far to open directly, and goes to the first page', () => {
            nav.search = 'page=900';
            server.error = true;
            server.errorBody = { status: 400, data: { code: 'page_too_deep' } };
            render(tree());
            expect(screen.getByRole('alert')).toHaveTextContent('That page is too far to open directly');
            server.error = false;
            fireEvent.click(screen.getByRole('button', { name: 'Go to the first page' }));
            expect(nav.search).toBe('');
            expect(lastQuery()).toMatchObject({ page: 1 });
        });
    });

    describe('the page scrolls as a whole', () => {
        it('has no nested scroll area in the table', () => {
            const { container } = renderTable();
            expect(container.querySelector('[style*="65vh"]')).toBeNull();
            expect(container.innerHTML).not.toContain('65vh');
        });
    });

    describe('accessibility', () => {
        it('has no WCAG A/AA violations in the filter bar, count, table and pager', async () => {
            vi.useRealTimers();
            server.items = Array.from({ length: 60 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            const { container } = renderTable();
            expect(await axeViolations(container)).toEqual([]);
            vi.useFakeTimers();
        });

        it('labels every filter and the sort', () => {
            renderTable();
            openFilters();
            ['Submitted from', 'Submitted until', 'Responder', 'Deletion request', 'Form version', 'Sort by', 'Rows per page'].forEach((label) => expect(screen.getByLabelText(label)).toBeInTheDocument());
            expect(screen.getByRole('search', { name: 'Search, filter and sort responses' })).toBeInTheDocument();
        });
    });

    describe('the head: one row, the filters behind a button, what is in force as chips', () => {
        it('puts search, Filters, sort and export in one toolbar, with the filter fields closed', () => {
            renderTable();
            const toolbar = screen.getByRole('search', { name: 'Search, filter and sort responses' });
            expect(within(toolbar).getByPlaceholderText('Search by responder email')).toBeInTheDocument();
            const toggle = within(toolbar).getByRole('button', { name: 'Filters' });
            expect(toggle).toHaveAttribute('aria-expanded', 'false');
            expect(within(toolbar).getByLabelText('Sort by')).toBeInTheDocument();
            // the fields are not drawn until the button opens them
            expect(screen.queryByLabelText('Submitted from')).toBeNull();
            expect(screen.queryByRole('list', { name: 'Active filters' })).toBeNull();
            fireEvent.click(toggle);
            expect(toggle).toHaveAttribute('aria-expanded', 'true');
            const panel = document.getElementById(toggle.getAttribute('aria-controls')!)!;
            expect(within(panel).getByLabelText('Submitted from')).toBeInTheDocument();
            expect(within(panel).getByLabelText('Form version')).toBeInTheDocument();
            fireEvent.click(toggle);
            expect(screen.queryByLabelText('Submitted from')).toBeNull();
        });

        it('lists what is in force as chips, also while the fields are closed, and counts it on the button', () => {
            nav.search = 'from=2026-01-05&to=2026-01-09&who=known&status=pending&version=1';
            render(tree());
            const chips = within(screen.getByRole('list', { name: 'Active filters' }));
            ['From 5 January 2026', 'Until 9 January 2026', 'Responder: Identified', 'Deletion request: Deletion requested', 'Version 1 (current)'].forEach((label) => expect(chips.getByText(label)).toBeInTheDocument());
            expect(screen.getByRole('button', { name: 'Filters, 5 active filters' })).toBeInTheDocument();
        });

        it('removes one filter with its chip, leaves the rest and puts focus back on the Filters button', () => {
            nav.search = 'who=known&status=pending&sort=oldest';
            render(tree());
            fireEvent.click(screen.getByRole('button', { name: 'Remove filter: Responder: Identified' }));
            expect(nav.search).toBe('sort=oldest&status=pending');
            expect(screen.queryByText('Responder: Identified')).toBeNull();
            expect(screen.getByRole('button', { name: /^Filters(,|$)/ })).toHaveFocus();
            fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
            expect(nav.search).toBe('sort=oldest');
            expect(screen.queryByRole('list', { name: 'Active filters' })).toBeNull();
        });

        it('moves focus to the Filters button when "Clear filters" is used, and when the empty state\'s button is', () => {
            nav.search = 'who=known&status=pending';
            const { unmount } = render(tree());
            fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
            expect(screen.getByRole('button', { name: /^Filters(,|$)/ })).toHaveFocus();
            unmount();
            // nothing matches: the empty state's own button goes with the filters, and focus must not fall to <body>
            server.items = [item('r1', 'a@example.com', 'blue')];
            nav.search = 'who=anonymous';
            render(tree());
            const clear = screen.getAllByRole('button', { name: 'Clear filters' }).at(-1)!;
            clear.focus();
            fireEvent.click(clear);
            expect(screen.getByRole('button', { name: /^Filters(,|$)/ })).toHaveFocus();
        });

        it('opens the panel with focus on its first field, and Escape closes it back onto the button', () => {
            renderTable();
            const toggle = screen.getByRole('button', { name: /^Filters(,|$)/ });
            fireEvent.click(toggle);
            expect(screen.getByLabelText('Submitted from')).toHaveFocus();
            fireEvent.keyDown(screen.getByLabelText('Submitted from'), { key: 'Escape' });
            expect(screen.queryByLabelText('Submitted from')).toBeNull();
            expect(toggle).toHaveFocus();
        });

        it('has no WCAG A/AA violations with the fields open and chips showing', async () => {
            vi.useRealTimers();
            nav.search = 'who=known&version=1';
            const { container } = render(tree());
            openFilters();
            expect(await axeViolations(container)).toEqual([]);
            vi.useFakeTimers();
        });
    });

    describe('on a phone: a card for each response', () => {
        const phone = () => {
            window.innerWidth = 375;
        };
        afterEach(() => {
            window.innerWidth = 1024;
        });

        it('draws cards instead of the table, each a link named by who answered', () => {
            phone();
            const { container } = renderTable();
            expect(container.querySelector('[role="table"]')).toBeNull();
            const list = screen.getByRole('list', { name: 'Responses on this page' });
            expect(within(list).getAllByRole('listitem')).toHaveLength(4);
            const link = within(list).getByRole('link', { name: /^Open response from known\.a@example\.com, submitted 2 January 2026 at \d\d:\d\d$/ });
            expect(link).toHaveAttribute('href', '/acme/dashboard/forms/form-1/responses/r1');
            expect(within(list).getByRole('link', { name: /^Open anonymous response, submitted 2 January 2026 at \d\d:\d\d$/ })).toHaveAttribute('href', '/acme/dashboard/forms/form-1/responses/r4');
        });

        it('gives every card its own link name, also for anonymous responses (the time tells them apart)', () => {
            phone();
            server.items = [
                { ...item('a1', null, 'blue'), createdAt: '2026-01-02T03:04:05Z' },
                { ...item('a2', null, 'blue'), createdAt: '2026-01-03T09:30:00Z' }
            ];
            renderTable();
            const names = within(screen.getByRole('list', { name: 'Responses on this page' })).getAllByRole('link').map((link) => link.getAttribute('aria-label'));
            expect(new Set(names).size).toBe(2);
            names.forEach((name) => expect(name).toMatch(/^Open anonymous response, submitted \d+ January 2026 at \d\d:\d\d$/));
        });

        it('says when it was submitted, in the viewer\'s time, and the first answer', () => {
            phone();
            renderTable();
            const card = within(screen.getByRole('list', { name: 'Responses on this page' }).firstElementChild as HTMLElement);
            expect(card.getByText(/^Submitted 2 January 2026 at \d\d:\d\d/)).toBeInTheDocument();
            expect(card.getByText('Favourite colour')).toBeInTheDocument();
            expect(card.getByText('blue')).toBeInTheDocument();
        });

        it('keeps the head, the count and the pager usable and the page free of a sideways scroll', () => {
            phone();
            server.items = Array.from({ length: 60 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            renderTable();
            expect(screen.getByRole('button', { name: /^Filters(,|$)/ })).toBeInTheDocument();
            expect(screen.getByRole('status')).toHaveTextContent('Showing 1–25 of 60');
            next();
            expect(lastQuery().page).toBe(2);
        });

        it('has no WCAG A/AA violations', async () => {
            vi.useRealTimers();
            phone();
            const { container } = renderTable();
            expect(await axeViolations(container)).toEqual([]);
            vi.useFakeTimers();
        });
    });

    describe('Dutch', () => {
        afterEach(async () => {
            await i18n.changeLanguage('en');
        });

        it('has the filters, count and pager in Dutch', async () => {
            i18n.addResourceBundle('nl', 'common', commonNl, true, true);
            await i18n.changeLanguage('nl');
            server.items = Array.from({ length: 60 }, (_, index) => item(`p${index}`, `person${index}@example.com`, 'blue'));
            renderTable();
            openFilters();
            expect(screen.getByLabelText('Ingediend vanaf')).toBeInTheDocument();
            expect(screen.getByLabelText('Ingediend tot en met')).toBeInTheDocument();
            expect(screen.getByLabelText('Verwijderverzoek')).toBeInTheDocument();
            expect(screen.getByLabelText('Formulierversie')).toBeInTheDocument();
            expect(screen.getByLabelText('Sorteren op')).toBeInTheDocument();
            expect(screen.getByLabelText('Rijen per pagina')).toBeInTheDocument();
            expect(screen.getByRole('status')).toHaveTextContent('1–25 van 60 getoond');
            expect(screen.getAllByLabelText('Volgende pagina').length).toBeGreaterThan(0);
        });

        const nlBundle = async () => {
            i18n.addResourceBundle('nl', 'common', commonNl, true, true);
            await i18n.changeLanguage('nl');
        };

        it('has the head, the chips, the table and its dates in Dutch', async () => {
            await nlBundle();
            nav.search = 'from=2026-01-05&who=known&version=1';
            render(tree());
            const toolbar = screen.getByRole('search', { name: 'Reacties zoeken, filteren en sorteren' });
            expect(within(toolbar).getByPlaceholderText('Zoeken op e-mailadres van de respondent')).toBeInTheDocument();
            expect(within(toolbar).getByRole('button', { name: /^Filters(,|$)/ })).toBeInTheDocument();
            const chips = within(screen.getByRole('list', { name: 'Actieve filters' }));
            ['Vanaf 5 januari 2026', 'Respondent: Geïdentificeerd', 'Versie 1 (huidig)'].forEach((label) => expect(chips.getByText(label)).toBeInTheDocument());
            expect(screen.getByRole('button', { name: 'Filter verwijderen: Respondent: Geïdentificeerd' })).toBeInTheDocument();
            expect(screen.getByRole('button', { name: 'Filters wissen' })).toBeInTheDocument();
            expect(screen.getByText('Respondent-ID')).toBeInTheDocument();
            expect(screen.getAllByText(/^2 januari 2026 om \d\d:\d\d$/).length).toBeGreaterThan(0);
            expect(screen.getAllByRole('link', { name: 'Reactie openen' }).length).toBeGreaterThan(0);
            expect(screen.getByRole('region', { name: 'Reacties' })).toBeInTheDocument();
            // nothing of the table's chrome is left in English
            ['Anonymous', 'Open response', 'Responder ID', 'Filters and', 'Clear filters'].forEach((text) => expect(screen.queryByText(text)).toBeNull());
        });

        it('has the empty, no-match and error states in Dutch', async () => {
            await nlBundle();
            server.items = [];
            store.dispatch(setForm({ ...store.getState().form, responses: 0 } as any));
            const { unmount } = renderTable();
            expect(screen.getByText('Nog geen reacties')).toBeInTheDocument();
            expect(screen.getByText('Reacties verschijnen hier zodra iemand uw formulier invult.')).toBeInTheDocument();
            unmount();
            server.items = [item('r1', 'a@example.com', 'blue')];
            store.dispatch(setForm({ ...store.getState().form, responses: 1 } as any));
            renderTable();
            fireEvent.change(screen.getByPlaceholderText('Zoeken op e-mailadres van de respondent'), { target: { value: 'nobody' } });
            act(() => {
                vi.advanceTimersByTime(600);
            });
            expect(screen.getByText('Geen reacties gevonden')).toBeInTheDocument();
            expect(screen.getByText(/Niets komt overeen met/)).toHaveTextContent('nobody');
        });

        it('has the error state in Dutch with its Retry', async () => {
            await nlBundle();
            server.error = true;
            renderTable();
            expect(screen.getByRole('alert')).toHaveTextContent('Reacties konden niet worden geladen');
            expect(screen.getByRole('button', { name: 'Opnieuw proberen' })).toBeInTheDocument();
        });

        it('has the cards of a phone in Dutch', async () => {
            await nlBundle();
            window.innerWidth = 375;
            try {
                renderTable();
                const list = screen.getByRole('list', { name: 'Reacties op deze pagina' });
                expect(within(list).getByRole('link', { name: /^Reactie van known\.a@example\.com, ingediend 2 januari 2026 om \d\d:\d\d, openen$/ })).toBeInTheDocument();
                expect(within(list).getByRole('link', { name: /^Anonieme reactie, ingediend 2 januari 2026 om \d\d:\d\d, openen$/ })).toBeInTheDocument();
                expect(within(list).getAllByText(/^Ingediend 2 januari 2026 om \d\d:\d\d/).length).toBe(4);
            } finally {
                window.innerWidth = 1024;
            }
        });

        it('has no WCAG A/AA violations in Dutch', async () => {
            await nlBundle();
            vi.useRealTimers();
            nav.search = 'who=known';
            const { container } = render(tree());
            openFilters();
            expect(await axeViolations(container)).toEqual([]);
            vi.useFakeTimers();
        });

        it('has every staff key in Dutch, and the same placeholders', () => {
            const placeholders = (value: string) => (value.match(/{{\w+}}/g) ?? []).sort();
            const en = (commonEn as any).RESPONSES_STAFF as Record<string, string>;
            const nl = (commonNl as any).RESPONSES_STAFF as Record<string, string>;
            expect(Object.keys(nl).sort()).toEqual(Object.keys(en).sort());
            Object.keys(en).forEach((key) => expect(placeholders(nl[key]), key).toEqual(placeholders(en[key])));
        });

        it('has every new English key in Dutch, and the same placeholders', () => {
            const en = (commonEn as any).RESPONSES_LIST as Record<string, string>;
            const nl = (commonNl as any).RESPONSES_LIST as Record<string, string>;
            expect(Object.keys(nl).sort()).toEqual(Object.keys(en).sort());
            const placeholders = (value: string) => (value.match(/{{\w+}}/g) ?? []).sort();
            Object.keys(en).forEach((key) => expect(placeholders(nl[key]), key).toEqual(placeholders(en[key])));
        });
    });
});
