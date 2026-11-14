// The Report page: the Overview from the form's questions, the report in the address, one request for every card,
// the refusals (too many rows, rate limit, busy, timeout, unreadable answers), an empty form, the switch off, and Dutch.
import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { axeViolations } from '@app/test/axe';
import { catalogue, figures } from '@app/test/report-fixtures';
import { ReportClause, ReportView, ReportCardDef, ReportDefinition, ReportResult, ReportViewList, cardsParam, parseCardsParam } from '@app/utils/report';

import ReportPage from './report-page';

const PATH = '/acme/dashboard/forms/form-1/responses/report';

// the server: what the hooks answer, and what they were asked
const server: {
    permissions: Set<string>;
    enabled: boolean;
    catalogue: typeof catalogue | undefined;
    catalogueError: unknown;
    queryError: unknown;
    result: (definition: ReportDefinition) => ReportResult;
    fetching: boolean;
    stale: boolean;
    asked: Array<{ definition: ReportDefinition; skip: boolean }>;
    refetch: ReturnType<typeof vi.fn>;
    refetchFields: ReturnType<typeof vi.fn>;
    views: ReportViewList | undefined;
    refetchViews: ReturnType<typeof vi.fn>;
    options: Array<Record<string, unknown>>;
    create: ReturnType<typeof vi.fn>;
    update: ReturnType<typeof vi.fn>;
    remove: ReturnType<typeof vi.fn>;
    drill: ReturnType<typeof vi.fn>;
    exportCard: ReturnType<typeof vi.fn>;
} = {} as never;

const nav = { search: '', listeners: new Set<() => void>(), pushes: [] as string[], replaces: [] as string[] };
const goTo = (url: string, record: string[]) => {
    record.push(url);
    nav.search = url.includes('?') ? url.split('?')[1] : '';
    nav.listeners.forEach((listener) => listener());
};
vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: (url: string) => goTo(url, nav.pushes), replace: (url: string) => goTo(url, nav.replaces) }),
    usePathname: () => PATH,
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
vi.mock('next/link', () => ({ default: ({ href, children, ...rest }: any) => <a href={href}>{children}</a> }));
vi.mock('@app/store/hooks', () => ({
    useAppSelector: (selector: (state: unknown) => unknown) => selector({ form: { formId: 'form-1', version: 3, title: 'Staff survey' }, workspace: { id: 'ws-1', workspaceName: 'acme' } })
}));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => server.permissions.has(permission), reportingEnabled: server.enabled, ready: true })
}));
vi.mock('@app/store/workspaces/api', () => ({
    useGetReportFieldsQuery: (_args: unknown, options: { skip?: boolean }) => ({ data: options.skip ? undefined : server.catalogue, isLoading: false, error: server.catalogueError, refetch: server.refetchFields }),
    useQueryReportQuery: (args: { definition: ReportDefinition }, options: { skip?: boolean }) => {
        server.asked.push({ definition: args.definition, skip: !!options.skip });
        server.options.push(options);
        const figures = options.skip || server.queryError ? undefined : server.result(args.definition);
        // `currentData` is the answer for this very definition; `data` would be the last one it got
        return { data: figures, currentData: server.stale ? undefined : figures, error: server.queryError, isError: !!server.queryError, isFetching: server.fetching, refetch: server.refetch };
    },
    useGetReportViewsQuery: (_args: unknown, options: { skip?: boolean }) => ({ data: options.skip ? undefined : server.views, isLoading: false, isError: false, refetch: server.refetchViews }),
    useCreateReportViewMutation: () => [server.create, { isLoading: false }],
    useUpdateReportViewMutation: () => [server.update, { isLoading: false }],
    useDeleteReportViewMutation: () => [server.remove, { isLoading: false }],
    useGetReportResponsesMutation: () => [server.drill],
    useExportReportCardMutation: () => [server.exportCard]
}));
// the browser's download is handed the file instead
const handed: Array<{ blob: Blob; fileName: string }> = [];
vi.mock('@app/utils/response-export', async (importOriginal) => ({
    ...(await importOriginal<typeof import('@app/utils/response-export')>()),
    downloadBlob: (blob: Blob, fileName: string) => {
        handed.push({ blob, fileName });
    }
}));

const cardsInUrl = (url: string): ReportCardDef[] | undefined => parseCardsParam(new URLSearchParams(url.split('?')[1] ?? '').get('cards'));
const lastAsked = () => server.asked.filter((call) => !call.skip).at(-1)?.definition as ReportDefinition;

beforeEach(() => {
    server.permissions = new Set([WorkspacePermission.RESPONSE_READ, WorkspacePermission.ANALYTICS_READ]);
    server.enabled = true;
    server.catalogue = catalogue;
    server.catalogueError = undefined;
    server.queryError = undefined;
    server.result = (definition) => figures(definition);
    server.fetching = false;
    server.stale = false;
    server.asked = [];
    server.refetch = vi.fn();
    server.refetchFields = vi.fn();
    server.views = { views: [], canShare: true, limits: { nameMax: 80, formViews: 50, privateViews: 20 } };
    server.refetchViews = vi.fn();
    server.options = [];
    server.create = vi.fn();
    server.update = vi.fn();
    server.remove = vi.fn();
    server.drill = vi.fn();
    server.exportCard = vi.fn();
    handed.length = 0;
    nav.search = '';
    nav.pushes = [];
    nav.replaces = [];
});

afterEach(async () => {
    await i18n.changeLanguage('en');
});

const renderPage = () => render(<ReportPage />);

describe('the Overview', () => {
    it('shows a card per reportable question after the response count and the responses over time, and asks for them all at once', () => {
        renderPage();
        expect(screen.getByRole('heading', { level: 2, name: 'Report' })).toBeInTheDocument();
        expect(screen.getByText(/Counts and averages of the answers to this form/)).toBeInTheDocument();
        const titles = screen.getAllByRole('figure').map((figure) => figure.getAttribute('aria-labelledby')).map((id) => document.getElementById(id as string)?.textContent);
        expect(titles).toEqual(['Responses', 'Responses over time', 'Which team are you in?', 'Which tools do you use?', 'How satisfied are you?', 'Average · Years at the organisation', 'Do you work remotely?']);
        // one request, with every card, the viewer's zone and no filter
        const asked = server.asked.filter((call) => !call.skip);
        expect(new Set(asked.map((call) => JSON.stringify(call.definition))).size).toBe(1);
        expect(lastAsked().cards).toHaveLength(7);
        expect(lastAsked().filters).toEqual({});
        expect(lastAsked().tz).toBeTruthy();
        expect(screen.getByText(/Days follow your time zone/)).toBeInTheDocument();
    });

    it('links back to the Responses list in the breadcrumb', () => {
        renderPage();
        const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' });
        expect(within(crumbs).getByRole('link', { name: 'Responses' })).toHaveAttribute('href', '/acme/dashboard/forms/form-1/responses');
        expect(within(crumbs).getByText('Report')).toHaveAttribute('aria-current', 'page');
    });

    it('carries the list filters of the address into the definition', () => {
        nav.search = 'from=2026-10-01&to=2026-10-31&status=none&who=known&version=2&sort=oldest&page=3';
        renderPage();
        const filters = lastAsked().filters;
        expect(filters.submittedFrom).toBe(new Date(2026, 9, 1).toISOString());
        expect(filters.submittedTo).toBe(new Date(2026, 10, 1).toISOString());
        expect(filters.status).toEqual(['none']);
        expect(filters.respondent).toBe('known');
        expect(filters.formVersion).toEqual([2]);
        // the sort is not a report filter, and the filter bar has no sort
        expect(screen.queryByLabelText('Sort')).toBeNull();
        expect(screen.getByRole('button', { name: /Filters/ })).toBeInTheDocument();
    });

    it('offers "Show all" for a form with more questions than the Overview lists', () => {
        server.catalogue = { ...catalogue, fields: Array.from({ length: 15 }, (_, index) => ({ ...catalogue.fields[0], key: `q:f${index}`, label: `Question ${index}` })) };
        renderPage();
        expect(lastAsked().cards).toHaveLength(2 + 12);
        fireEvent.click(screen.getByRole('button', { name: 'Show all 15 questions' }));
        expect(nav.replaces.at(-1)).toContain('all=1');
    });
});

describe('the cards live in the address', () => {
    it('removes a card by writing the others into the address, and offers the way back to the Overview', () => {
        const { rerender } = renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Remove Do you work remotely?' }));
        const cards = cardsInUrl(nav.replaces.at(-1) as string) as ReportCardDef[];
        expect(cards).toHaveLength(6);
        expect(cards.map((card) => card.id)).not.toContain('q5');
        rerender(<ReportPage />);
        expect(screen.queryByText('Do you work remotely?')).toBeNull();
        expect(lastAsked().cards).toHaveLength(6);
        fireEvent.click(screen.getByRole('button', { name: 'Back to the overview' }));
        expect(nav.replaces.at(-1)).toBe(PATH);
    });

    it('moves a card up or down', () => {
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Move Which team are you in? down' }));
        const cards = cardsInUrl(nav.replaces.at(-1) as string) as ReportCardDef[];
        expect(cards.map((card) => card.id).slice(2, 4)).toEqual(['q2', 'q1']);
    });

    it('adds a card from a labelled form: the question to group by, what to show, and how', () => {
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Add card' }));
        const form = screen.getByRole('form', { name: 'Add a card' });
        fireEvent.change(within(form).getByLabelText('Group by'), { target: { value: 'source' } });
        fireEvent.change(within(form).getByLabelText('Show as'), { target: { value: 'donut' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Add' }));
        const cards = cardsInUrl(nav.replaces.at(-1) as string) as ReportCardDef[];
        expect(cards).toHaveLength(8);
        expect(cards.at(-1)).toMatchObject({ kind: 'donut', dimension: { field: 'source' }, measures: [{ agg: 'count' }] });
    });

    it('opens a report from an address that carries cards, and ignores one that is malformed', () => {
        nav.search = 'cards=not-a-report';
        renderPage();
        expect(lastAsked().cards).toHaveLength(7);
    });

    it('changes a filter through the filter bar and keeps the cards', () => {
        nav.search = `cards=${cardsParam([{ id: 'c1', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }] }])}`;
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: /Filters/ }));
        fireEvent.change(screen.getByLabelText('Form version'), { target: { value: '2' } });
        expect(nav.pushes.at(-1)).toContain('version=2');
        expect(cardsInUrl(nav.pushes.at(-1) as string)).toHaveLength(1);
    });
});

describe('refusals and notices', () => {
    it('too many rows: says how many, and offers to narrow by date or by version', () => {
        server.queryError = { status: 413, data: { code: 'too_many_rows', count: 25318, max: 20000 } };
        renderPage();
        const alert = screen.getByRole('alert');
        expect(alert).toHaveTextContent('This selection has 25,318 responses. Narrow the dates to at most 20,000 to see the figures.');
        fireEvent.click(within(alert).getByRole('button', { name: 'Only the last 30 days' }));
        expect(nav.pushes.at(-1)).toMatch(/from=\d{4}-\d{2}-\d{2}/);
    });

    it('too many rows: narrows to the current version', () => {
        server.queryError = { status: 413, data: { code: 'too_many_rows', count: 25318, max: 20000 } };
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Only the current version (version 3)' }));
        expect(nav.pushes.at(-1)).toContain('version=3');
    });

    it.each([
        ['rate_limited', 429, 'Too many report requests in a short time. Try again in a moment.'],
        ['report_busy', 429, 'Other reports are being computed. Try again in a moment.'],
        ['report_timeout', 503, 'This report took too long to compute. Narrow the dates or the form version, or try again.'],
        [undefined, 500, 'The figures could not be loaded.']
    ])('%s: says so and retries', (code, status, text) => {
        server.queryError = { status, data: code ? { code } : undefined };
        renderPage();
        const alert = screen.getByRole('alert');
        expect(alert).toHaveTextContent(text);
        fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
        expect(server.refetch).toHaveBeenCalledTimes(1);
    });

    it('a catalogue that fails to load can be retried', () => {
        server.catalogue = undefined;
        server.catalogueError = { status: 500 };
        renderPage();
        fireEvent.click(within(screen.getByRole('alert')).getByRole('button', { name: 'Try again' }));
        expect(server.refetchFields).toHaveBeenCalledTimes(1);
    });

    it('says some answers could not be read and are left out', () => {
        server.result = (definition) => figures(definition, 212, ['unreadable_answers']);
        renderPage();
        expect(screen.getByText('Some answers could not be read and are left out of these figures.')).toBeInTheDocument();
    });

    it('an empty form says so, in place of cards of zeros', () => {
        server.result = (definition) => figures(definition, 0);
        renderPage();
        expect(screen.getByText('No responses yet')).toBeInTheDocument();
        expect(screen.getByText('This report fills in as soon as the form has responses.')).toBeInTheDocument();
        expect(screen.queryByRole('figure')).toBeNull();
    });

    it('a filter that selects nothing says that, not that the form is empty', () => {
        nav.search = 'who=known';
        server.result = (definition) => figures(definition, 0);
        renderPage();
        expect(screen.getByText('No responses match these filters.')).toBeInTheDocument();
        expect(screen.queryByText('No responses yet')).toBeNull();
    });

    it('a form with no reportable question says so', () => {
        server.catalogue = { ...catalogue, fields: [] };
        renderPage();
        expect(screen.getByText('No question of this form can be used in a report yet.')).toBeInTheDocument();
    });

    it('announces loading and arrival in a polite status region', async () => {
        server.fetching = true;
        const { rerender } = renderPage();
        const status = () => screen.getByTestId('report-live');
        await waitFor(() => expect(status()).toHaveTextContent('Updating figures'));
        server.fetching = false;
        rerender(<ReportPage />);
        await waitFor(() => expect(status()).toHaveTextContent('Figures updated: 212 responses.'));
    });
});

describe('the switch and the permissions', () => {
    it('with reports off the page is "not turned on", and asks the server for nothing', () => {
        server.enabled = false;
        renderPage();
        expect(screen.getByText('Reports are not turned on yet.')).toBeInTheDocument();
        expect(screen.queryByRole('figure')).toBeNull();
        expect(server.asked.every((call) => call.skip)).toBe(true);
    });

    it.each([[WorkspacePermission.ANALYTICS_READ], [WorkspacePermission.RESPONSE_READ]])('without %s it is the same page and asks for nothing', (missing) => {
        server.permissions.delete(missing);
        renderPage();
        expect(screen.getByText('Reports are not turned on yet.')).toBeInTheDocument();
        expect(server.asked.every((call) => call.skip)).toBe(true);
    });
});

describe('Dutch', () => {
    it('is Rapport, with the page, the cards and the groups in Dutch', async () => {
        await i18n.changeLanguage('nl');
        renderPage();
        expect(screen.getByRole('heading', { level: 2, name: 'Rapport' })).toBeInTheDocument();
        expect(screen.getByText(/Aantallen en gemiddelden van de antwoorden/)).toBeInTheDocument();
        expect(screen.getByRole('figure', { name: 'Reacties' })).toBeInTheDocument();
        expect(screen.getByRole('figure', { name: 'Reacties in de tijd' })).toBeInTheDocument();
        const remote = screen.getByRole('figure', { name: 'Do you work remotely?' });
        expect(remote).toHaveTextContent('Ja');
        expect(remote).toHaveTextContent('Nee');
        expect(screen.getByRole('button', { name: 'Kaart toevoegen' })).toBeInTheDocument();
        expect(screen.getByText(/Dagen volgen uw tijdzone/)).toBeInTheDocument();
        expect(within(screen.getByRole('navigation', { name: 'Kruimelpad' })).getByRole('link', { name: 'Reacties' })).toBeInTheDocument();
    });

    it('says the refusals in Dutch', async () => {
        await i18n.changeLanguage('nl');
        server.queryError = { status: 413, data: { code: 'too_many_rows', count: 25318, max: 20000 } };
        renderPage();
        expect(screen.getByRole('alert')).toHaveTextContent('Deze selectie heeft 25.318 reacties. Beperk de periode tot ten hoogste 20.000 om de cijfers te zien.');
        expect(screen.getByRole('button', { name: 'Alleen de laatste 30 dagen' })).toBeInTheDocument();
    });
});

describe('axe', () => {
    it('finds no violation in the page, the refusal or the empty state', async () => {
        const { container, unmount } = renderPage();
        expect(await axeViolations(container)).toEqual([]);
        unmount();
        server.queryError = { status: 413, data: { code: 'too_many_rows', count: 25318, max: 20000 } };
        const refused = renderPage();
        expect(await axeViolations(refused.container)).toEqual([]);
        refused.unmount();
        server.queryError = undefined;
        server.result = (definition) => figures(definition, 0);
        const empty = renderPage();
        expect(await axeViolations(empty.container)).toEqual([]);
    });
});



const VIEW_ONE = 'a'.repeat(24);
const VIEW_TWO = 'b'.repeat(24);
const saved = (changes: Partial<ReportView> = {}): ReportView => ({
    id: VIEW_ONE,
    name: 'Teams only',
    scope: 'private',
    mine: true,
    ownerName: null,
    revision: 3,
    createdAt: null,
    updatedAt: null,
    definition: { v: 1, filters: { respondent: 'known', formVersion: [2] }, tz: 'UTC', cards: [{ id: 'team', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }] }, { id: 'total', kind: 'tile', measures: [{ agg: 'count' }] }] },
    canEdit: true,
    canDelete: true,
    ...changes
});
const withViews = (...views: ReportView[]) => {
    server.views = { views, canShare: true, limits: { nameMax: 80, formViews: 50, privateViews: 20 } };
};

describe('saved views on the page', () => {
    it('opens a view: its cards and filters are written into the address, with the view that was opened', () => {
        withViews(saved(), saved({ id: VIEW_TWO, name: 'Shared', scope: 'form', mine: false, ownerName: 'Sanne de Vries' }));
        renderPage();
        fireEvent.change(screen.getByRole('combobox', { name: 'Views' }), { target: { value: VIEW_ONE } });
        const url = nav.pushes.at(-1) as string;
        const query = new URLSearchParams(url.split('?')[1]);
        expect(query.get('view')).toBe(VIEW_ONE);
        expect(query.get('who')).toBe('known');
        expect(query.get('version')).toBe('2');
        expect(cardsInUrl(url)?.map((card) => card.id)).toEqual(['team', 'total']);
    });

    it('asks the server for the report of the opened view and says it is not changed', () => {
        withViews(saved());
        nav.search = `view=${VIEW_ONE}&who=known&version=2&cards=${cardsParam(saved().definition.cards)}`;
        renderPage();
        expect(screen.getByRole('combobox', { name: 'Views' })).toHaveValue(VIEW_ONE);
        expect(lastAsked().cards.map((card) => card.id)).toEqual(['team', 'total']);
        expect(lastAsked().filters.respondent).toBe('known');
        expect(screen.getByText('Only you can open this view.')).toBeInTheDocument();
        expect(screen.queryByText('Changed since it was saved')).toBeNull();
        expect(screen.queryByRole('button', { name: 'Update view' })).toBeNull();
    });

    it('notices a change to the report and offers to update the view, which keeps its address', () => {
        withViews(saved());
        nav.search = `view=${VIEW_ONE}&who=known&version=2&cards=${cardsParam(saved().definition.cards)}`;
        const { rerender } = renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Remove Which team are you in?' }));
        // a change keeps the view in the address
        expect(new URLSearchParams((nav.replaces.at(-1) as string).split('?')[1]).get('view')).toBe(VIEW_ONE);
        rerender(<ReportPage />);
        expect(screen.getByText('Changed since it was saved')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Update view' })).toBeInTheDocument();
    });

    it('does not offer to update a view that holds a card this person cannot have answered, only to save a new one', () => {
        const gone = { id: 'gone', kind: 'bar' as const, dimension: { field: 'q:not-visible-to-me' }, measures: [{ agg: 'count' as const }] };
        const base = saved();
        const withHidden = saved({ definition: { ...base.definition, cards: [...base.definition.cards, gone] } });
        withViews(withHidden);
        nav.search = `view=${VIEW_ONE}&who=known&version=2&cards=${cardsParam(withHidden.definition.cards)}`;
        const { rerender } = renderPage();
        // the cards the person can have answered are asked; the one they cannot is not
        expect(lastAsked().cards.map((card) => card.id)).toEqual(['team', 'total']);
        expect(screen.queryByRole('button', { name: 'Update view' })).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: 'Remove Which team are you in?' }));
        rerender(<ReportPage />);
        const update = screen.getByRole('button', { name: 'Update view' });
        expect(update).toBeDisabled();
        expect(update).toHaveAccessibleDescription(/1 card of this view cannot be shown to you/);
        expect(screen.getByRole('button', { name: 'Save as new view' })).toBeEnabled();
        expect(server.update).not.toHaveBeenCalled();
    });

    it('also notices a changed filter', () => {
        withViews(saved());
        nav.search = `view=${VIEW_ONE}&who=known&version=2&cards=${cardsParam(saved().definition.cards)}`;
        const { rerender } = renderPage();
        fireEvent.click(screen.getByRole('button', { name: /Filters/ }));
        fireEvent.change(screen.getByLabelText('Form version'), { target: { value: '1' } });
        rerender(<ReportPage />);
        expect(screen.getByText('Changed since it was saved')).toBeInTheDocument();
    });

    it('goes back to the Overview with the Overview choice, keeping the filters', () => {
        withViews(saved());
        nav.search = `view=${VIEW_ONE}&who=known&cards=${cardsParam(saved().definition.cards)}`;
        renderPage();
        fireEvent.change(screen.getByRole('combobox', { name: 'Views' }), { target: { value: '' } });
        const query = new URLSearchParams((nav.pushes.at(-1) as string).split('?')[1]);
        expect(query.get('who')).toBe('known');
        expect(query.has('view')).toBe(false);
        expect(query.has('cards')).toBe(false);
    });

    it('says so when the address names a view the member cannot open, and shows the Overview', () => {
        withViews(saved());
        nav.search = `view=${VIEW_TWO}`;
        renderPage();
        expect(screen.getByText('This view no longer exists, or it is not one you can open.')).toBeInTheDocument();
        expect(lastAsked().cards).toHaveLength(7);
    });

    it('takes no notice of a view that is not an id', () => {
        withViews(saved());
        nav.search = 'view=../../x';
        renderPage();
        expect(screen.queryByText('This view no longer exists, or it is not one you can open.')).toBeNull();
        expect(screen.getByRole('combobox', { name: 'Views' })).toHaveValue('');
    });

    it('saves the report on screen: the definition asked for, without a card the form cannot answer', async () => {
        server.create.mockReturnValue({ unwrap: () => Promise.resolve(saved({ id: VIEW_TWO })) });
        nav.search = `cards=${cardsParam([{ id: 'gone', kind: 'bar', dimension: { field: 'q:gone' }, measures: [{ agg: 'count' }] }, { id: 'total', kind: 'tile', measures: [{ agg: 'count' }] }])}`;
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Save view' }));
        const form = screen.getByRole('form', { name: 'Save view' });
        fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Totals' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Save view' }));
        await waitFor(() => expect(server.create).toHaveBeenCalled());
        const sent = server.create.mock.calls[0][0];
        expect(sent).toMatchObject({ workspaceId: 'ws-1', formId: 'form-1', name: 'Totals', scope: 'private' });
        expect(sent.definition.cards.map((card: ReportCardDef) => card.id)).toEqual(['total']);
        // the new view is marked in the address
        await waitFor(() => expect(new URLSearchParams((nav.replaces.at(-1) as string).split('?')[1]).get('view')).toBe(VIEW_TWO));
    });

    it('is Weergaven in Dutch', async () => {
        await i18n.changeLanguage('nl');
        withViews(saved());
        renderPage();
        expect(screen.getByRole('combobox', { name: 'Weergaven' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Weergave opslaan' })).toBeInTheDocument();
    });

    it('finds no axe violation with a view open', async () => {
        withViews(saved(), saved({ id: VIEW_TWO, name: 'Shared', scope: 'form', mine: false, ownerName: null }));
        nav.search = `view=${VIEW_TWO}`;
        const { container } = renderPage();
        expect(await axeViolations(container)).toEqual([]);
    });
});

describe('the figures of the definition on screen', () => {
    it('does not ask again because a tab got the focus or the network came back (a pass can read 20,000 responses)', () => {
        renderPage();
        const options = server.options.at(-1) as Record<string, unknown>;
        expect(options.refetchOnFocus).toBe(false);
        expect(options.refetchOnReconnect).toBe(false);
    });

    it('draws no old figures under new labels: the cards of an edited report wait for their own', () => {
        server.stale = true;
        server.fetching = true;
        renderPage();
        expect(screen.queryByRole('img')).toBeNull();
        expect(screen.getAllByText('Loading figures').length).toBeGreaterThan(0);
        expect(screen.queryByText('212')).toBeNull();
    });
});


const WHERE: ReportClause[] = [{ field: 'q:team', op: 'is', value: 'north' }];
/** A saved view that carries conditions on answers, open in the address: the page restores them from the server. */
const viewWithWhere = (where: ReportClause[] = WHERE, changes: Partial<ReportView> = {}) => {
    const view = saved({ definition: { ...saved().definition, filters: { where } }, ...changes });
    withViews(view);
    nav.search = `view=${VIEW_ONE}&cards=${cardsParam(view.definition.cards)}`;
    return view;
};
const addCondition = (value = 'south') => {
    fireEvent.click(screen.getByRole('button', { name: 'Add answer filter' }));
    const form = screen.getByRole('form', { name: 'Add answer filter' });
    fireEvent.change(within(form).getByLabelText('Value'), { target: { value } });
    fireEvent.click(within(form).getByRole('button', { name: 'Add' }));
};
/** Every address the page wrote, and every link it drew. */
const addressesWritten = () => [...nav.pushes, ...nav.replaces];
const linksDrawn = () => Array.from(document.querySelectorAll('a')).map((a) => a.getAttribute('href') ?? '');

describe('answer filters on the page', () => {
    it('restores the conditions of the view the address names, from the server, and says how many responses met them', () => {
        viewWithWhere();
        server.result = (definition) => figures(definition, 74);
        renderPage();
        expect(lastAsked().filters.where).toEqual(WHERE);
        expect(screen.getByRole('list', { name: 'Answer filters in force' })).toHaveTextContent('Which team are you in? is North');
        expect(screen.getByRole('figure', { name: 'Responses' })).toHaveTextContent('n = 74');
    });

    it('shows a card grouped by a status with its reason, and does not ask for it, while a condition on an answer is in force', () => {
        const statusCard: ReportCardDef = { id: 'state', kind: 'bar', dimension: { field: 'status' }, measures: [{ agg: 'count' }] };
        const view = saved({ definition: { ...saved().definition, filters: { where: WHERE }, cards: [...saved().definition.cards, statusCard] } });
        withViews(view);
        nav.search = `view=${VIEW_ONE}&cards=${cardsParam(view.definition.cards)}`;
        renderPage();
        expect(lastAsked().filters.where).toEqual(WHERE);
        expect(lastAsked().cards.map((card) => card.id)).toEqual(['team', 'total']);
        expect(screen.getAllByText(/cannot be combined with a condition on an answer/).length).toBe(1);
        // the view is not offered an Update that would drop it, and a save sends it so the server says why
        expect(screen.queryByRole('button', { name: 'Update view' })).toBeNull();
    });

    it('asks for the same card as before once the condition is gone', () => {
        const statusCard: ReportCardDef = { id: 'state', kind: 'bar', dimension: { field: 'status' }, measures: [{ agg: 'count' }] };
        nav.search = `cards=${cardsParam([statusCard])}`;
        renderPage();
        expect(lastAsked().cards.map((card) => card.id)).toEqual(['state']);
        expect(screen.queryByText(/cannot be combined with a condition on an answer/)).toBeNull();
    });

    it('takes no condition from the address: a `where` parameter means nothing', () => {
        nav.search = 'who=known&where=eyJmaWVsZCI6InE6dGVhbSJ9';
        renderPage();
        expect(lastAsked().filters.where).toBeUndefined();
        expect(screen.queryByRole('list', { name: 'Answer filters in force' })).toBeNull();
    });

    it('keeps an added condition in the page, asks for it, and puts nothing about it in the address', () => {
        renderPage();
        addCondition('south');
        expect(lastAsked().filters.where).toEqual([{ field: 'q:team', op: 'is', value: 'south' }]);
        expect(screen.getByRole('list', { name: 'Answer filters in force' })).toHaveTextContent('Which team are you in? is South');
        expect(addressesWritten()).toEqual([]);
    });

    it('removes one, and clears them all', () => {
        viewWithWhere([...WHERE, { field: 'q:score', op: '>=', value: 4 }]);
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Remove filter: Which team are you in? is North' }));
        expect(lastAsked().filters.where).toEqual([{ field: 'q:score', op: '>=', value: 4 }]);
        fireEvent.click(screen.getByRole('button', { name: 'Clear answer filters' }));
        expect(lastAsked().filters.where).toBeUndefined();
    });

    it('does not put the view back over a condition the person has changed since', () => {
        viewWithWhere();
        const { rerender } = renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Clear answer filters' }));
        rerender(<ReportPage />);
        rerender(<ReportPage />);
        expect(lastAsked().filters.where).toBeUndefined();
        expect(screen.getByText('Changed since it was saved')).toBeInTheDocument();
    });

    it('leaves a condition on a question the form no longer has out of the request, and says so', () => {
        viewWithWhere([{ field: 'q:gone', op: 'is_empty' }, ...WHERE]);
        renderPage();
        expect(lastAsked().filters.where).toEqual(WHERE);
        expect(screen.getByText(/q:gone has no answer \(This question is no longer in the form\.\)/)).toBeInTheDocument();
    });

    it('says a filter that selects nothing selected nothing', () => {
        viewWithWhere();
        server.result = (definition) => figures(definition, 0);
        renderPage();
        expect(screen.getByText('No responses match these filters.')).toBeInTheDocument();
    });

    it('is part of a saved view: opening one restores its conditions, and a report without them is a changed view', () => {
        const view = viewWithWhere();
        nav.search = '';
        const { rerender } = renderPage();
        fireEvent.change(screen.getByRole('combobox', { name: 'Views' }), { target: { value: VIEW_ONE } });
        expect(lastAsked().filters.where).toEqual(WHERE);
        expect(new URLSearchParams((nav.pushes.at(-1) as string).split('?')[1]).get('view')).toBe(VIEW_ONE);
        expect(view.definition.filters.where).toEqual(WHERE);
        // another view without conditions takes them away
        withViews(view, saved({ id: VIEW_TWO, name: 'Plain' }));
        rerender(<ReportPage />);
        fireEvent.change(screen.getByRole('combobox', { name: 'Views' }), { target: { value: VIEW_TWO } });
        expect(lastAsked().filters.where).toBeUndefined();
    });

    it('saves the conditions with the view', async () => {
        server.create.mockReturnValue({ unwrap: () => Promise.resolve(saved({ id: VIEW_TWO })) });
        renderPage();
        addCondition('south');
        fireEvent.click(screen.getByRole('button', { name: 'Save view' }));
        const form = screen.getByRole('form', { name: 'Save view' });
        fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'South only' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Save view' }));
        await waitFor(() => expect(server.create).toHaveBeenCalled());
        expect(server.create.mock.calls[0][0].definition.filters.where).toEqual([{ field: 'q:team', op: 'is', value: 'south' }]);
        // the saved view is the one on screen, with its conditions still in force
        await waitFor(() => expect(new URLSearchParams((nav.replaces.at(-1) as string).split('?')[1]).get('view')).toBe(VIEW_TWO));
        expect(lastAsked().filters.where).toEqual([{ field: 'q:team', op: 'is', value: 'south' }]);
    });

    it('is in Dutch', async () => {
        await i18n.changeLanguage('nl');
        viewWithWhere([{ field: 'q:years', op: '>=', value: 3 }]);
        renderPage();
        expect(screen.getByRole('list', { name: 'Actieve antwoordfilters' })).toHaveTextContent('is minstens 3');
        expect(screen.getByRole('button', { name: 'Antwoordfilter toevoegen' })).toBeInTheDocument();
    });
});

describe('the address never holds a condition on an answer', () => {
    const VALUES = ['south', '1987', '2026-03-09', '4500'];
    const noTrace = (text: string) => {
        expect(text).not.toMatch(/where/i);
        for (const value of VALUES) expect(text).not.toContain(value);
    };

    it('writes none through the router or into a link, whatever the page does', async () => {
        server.drill.mockReturnValue({ unwrap: () => Promise.resolve({ responses: [{ id: 'r1', submittedAt: '2026-10-05T10:00:00Z', formVersion: 2, respondent: 'known' }], cursor: null, scanned: 1, exhausted: true }) });
        server.create.mockReturnValue({ unwrap: () => Promise.resolve(saved({ id: VIEW_TWO })) });
        nav.search = `cards=${cardsParam([{ id: 'v', kind: 'table', dimension: { field: 'form_version' }, measures: [{ agg: 'count' }] }, { id: 'team', kind: 'bar', dimension: { field: 'q:team' }, measures: [{ agg: 'count' }] }])}&who=known`;
        const { rerender } = renderPage();
        // conditions of every kind of value
        addCondition('south');
        fireEvent.click(screen.getByRole('button', { name: 'Add answer filter' }));
        let form = screen.getByRole('form', { name: 'Add answer filter' });
        fireEvent.change(within(form).getByLabelText('Question'), { target: { value: 'q:years' } });
        fireEvent.change(within(form).getByLabelText('Value'), { target: { value: '1987' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Add' }));
        // change a filter and the cards (these do write an address: the list's filters and the cards)
        fireEvent.click(screen.getByRole('button', { name: /Filters/ }));
        fireEvent.change(screen.getByRole('combobox', { name: 'Form version' }), { target: { value: '2' } });
        rerender(<ReportPage />);
        fireEvent.click(screen.getAllByRole('button', { name: /^Move .* down$/ })[0]);
        rerender(<ReportPage />);
        // open the responses of a group, with the link to the list
        fireEvent.click(screen.getByRole('button', { name: 'Open these responses: Version 2' }));
        await screen.findByRole('table', { name: 'Responses in Version 2' });
        // save a view
        fireEvent.click(screen.getByRole('button', { name: 'Save view' }));
        form = screen.getByRole('form', { name: 'Save view' });
        fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Mine' } });
        fireEvent.click(within(form).getByRole('button', { name: 'Save view' }));
        await waitFor(() => expect(server.create).toHaveBeenCalled());
        // the conditions were asked for, and written nowhere
        expect(server.create.mock.calls[0][0].definition.filters.where).toHaveLength(2);
        expect(addressesWritten().length).toBeGreaterThan(0);
        for (const url of addressesWritten()) noTrace(decodeURIComponent(url));
        const links = linksDrawn();
        expect(links.length).toBeGreaterThan(0);
        for (const href of links) noTrace(decodeURIComponent(href));
        // the cards the address holds are only ids and enums
        for (const url of addressesWritten()) {
            const cards = new URLSearchParams(url.split('?')[1] ?? '').get('cards');
            if (cards) noTrace(Buffer.from(cards.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString());
        }
    });

    it('draws the link to the responses list with the plaintext filter only', async () => {
        server.drill.mockReturnValue({ unwrap: () => Promise.resolve({ responses: [], cursor: null, scanned: 0, exhausted: true }) });
        nav.search = `cards=${cardsParam([{ id: 'v', kind: 'table', dimension: { field: 'form_version' }, measures: [{ agg: 'count' }] }])}`;
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Open these responses: Version 2' }));
        const link = await screen.findByRole('link', { name: 'Open this group in the responses list' });
        expect(link.getAttribute('href')).toBe('/acme/dashboard/forms/form-1/responses?version=2');
    });

    it('has no link to the list at all while conditions are in force (the list cannot say them)', async () => {
        server.drill.mockReturnValue({ unwrap: () => Promise.resolve({ responses: [], cursor: null, scanned: 0, exhausted: true }) });
        nav.search = `cards=${cardsParam([{ id: 'v', kind: 'table', dimension: { field: 'form_version' }, measures: [{ agg: 'count' }] }])}`;
        renderPage();
        addCondition('south');
        fireEvent.click(screen.getByRole('button', { name: 'Open these responses: Version 2' }));
        await screen.findByRole('table', { name: 'Responses in Version 2' }).catch(() => undefined);
        expect(screen.queryByRole('link', { name: 'Open this group in the responses list' })).toBeNull();
    });
});

describe('drill-down on the page', () => {
    const open = (card = 'Which team are you in?') => {
        const figure = screen.getByRole('figure', { name: card });
        // a card that is already a table has no switch left to press
        const toggle = within(figure).queryByRole('button', { name: 'Show as table' });
        if (toggle) fireEvent.click(toggle);
        return figure;
    };
    const rowsReply = (n: number) => ({ unwrap: () => Promise.resolve({ responses: Array.from({ length: n }, (_, i) => ({ id: `r${i}`, submittedAt: '2026-10-05T10:00:00Z', formVersion: 2, respondent: 'known' })), cursor: null, scanned: n, exhausted: true }) });

    it('opens the responses of a group under the cards, asked with the definition on screen', async () => {
        nav.search = 'who=known';
        server.drill.mockReturnValue(rowsReply(2));
        renderPage();
        addCondition('south');
        const figure = open();
        fireEvent.click(within(figure).getByRole('button', { name: 'Open these responses: South' }));
        expect(await screen.findByRole('table', { name: 'Responses in South' })).toBeInTheDocument();
        const asked = server.drill.mock.calls.at(-1)?.[0];
        expect(asked).toMatchObject({ workspaceId: 'ws-1', formId: 'form-1', card: 'q1', group: 'south' });
        expect(asked.definition.filters.where).toEqual([{ field: 'q:team', op: 'is', value: 'south' }]);
        expect(asked.definition.filters.respondent).toBe('known');
    });

    it('closes, and goes away with its card', async () => {
        server.drill.mockReturnValue(rowsReply(1));
        const { rerender } = renderPage();
        fireEvent.click(within(open()).getByRole('button', { name: 'Open these responses: North' }));
        expect(await screen.findByRole('heading', { name: 'Responses in North' })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Close the list of responses' }));
        expect(screen.queryByRole('heading', { name: 'Responses in North' })).toBeNull();
        fireEvent.click(within(open()).getByRole('button', { name: 'Open these responses: North' }));
        expect(await screen.findByRole('heading', { name: 'Responses in North' })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Remove Which team are you in?' }));
        rerender(<ReportPage />);
        expect(screen.queryByRole('heading', { name: 'Responses in North' })).toBeNull();
    });

    it('links a plaintext group to the responses list with the same filter, over the list filters in force', async () => {
        nav.search = `cards=${cardsParam([{ id: 'v', kind: 'table', dimension: { field: 'form_version' }, measures: [{ agg: 'count' }] }])}&who=known`;
        server.drill.mockReturnValue(rowsReply(1));
        renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Open these responses: Version 2' }));
        const link = await screen.findByRole('link', { name: 'Open this group in the responses list' });
        const query = new URLSearchParams((link.getAttribute('href') as string).split('?')[1]);
        expect(link.getAttribute('href')).toMatch(/^\/acme\/dashboard\/forms\/form-1\/responses\?/);
        expect(query.get('version')).toBe('2');
        expect(query.get('who')).toBe('known');
    });

    it('finds no axe violation with the responses open', async () => {
        server.drill.mockReturnValue(rowsReply(2));
        const { container } = renderPage();
        fireEvent.click(within(open()).getByRole('button', { name: 'Open these responses: North' }));
        await screen.findByRole('table', { name: 'Responses in North' });
        expect(await axeViolations(container)).toEqual([]);
    });
});

describe('downloading a card as a CSV', () => {
    const file = (name?: string) => ({ unwrap: () => Promise.resolve({ blob: new Blob(['x']), fileName: name }) });
    const refusal = (status: number, code?: string) => ({ unwrap: () => Promise.reject({ status, data: code ? { code } : {} }) });
    const teamCard = () => screen.getByRole('figure', { name: 'Which team are you in?' });
    const mayExport = () => server.permissions.add(WorkspacePermission.RESPONSE_EXPORT);

    it('is offered on every card to a member who may export responses', () => {
        mayExport();
        renderPage();
        expect(screen.getAllByRole('button', { name: /^Download as CSV/ })).toHaveLength(7);
    });

    it('is not offered to a member who may read the report but not export', () => {
        renderPage();
        expect(screen.queryByRole('button', { name: /Download as CSV/ })).toBeNull();
    });

    it("asks for this card only, with the filters and the zone on screen, and hands the file over under the server's name", async () => {
        mayExport();
        server.exportCard.mockReturnValue(file('Staff survey - report.csv'));
        nav.search = 'who=known&version=2';
        renderPage();
        fireEvent.click(within(teamCard()).getByRole('button', { name: 'Download as CSV: Which team are you in?' }));
        await waitFor(() => expect(handed).toHaveLength(1));
        expect(handed[0].fileName).toBe('Staff survey - report.csv');
        const asked = server.exportCard.mock.calls.at(-1)?.[0];
        expect(asked).toMatchObject({ workspaceId: 'ws-1', formId: 'form-1' });
        expect(asked.card).toBe(asked.definition.cards[0].id);
        expect(asked.definition.cards).toHaveLength(1);
        expect(asked.definition.cards[0].dimension).toEqual({ field: 'q:team' });
        expect(asked.definition.filters).toMatchObject({ respondent: 'known', formVersion: [2] });
        expect(asked.definition.tz).toBeTruthy();
        expect(await within(teamCard()).findByRole('status')).toHaveTextContent('The file was downloaded.');
    });

    it('names the file after the form when the server offers no name', async () => {
        mayExport();
        server.exportCard.mockReturnValue(file(undefined));
        renderPage();
        fireEvent.click(within(teamCard()).getByRole('button', { name: /^Download as CSV/ }));
        await waitFor(() => expect(handed).toHaveLength(1));
        expect(handed[0].fileName).toBe('Staff survey.csv');
    });

    it.each([
        [403, undefined, 'You may not download this report.'],
        [429, 'rate_limited', 'You have downloaded this report as often as is allowed for now. Try again later.'],
        [429, 'report_busy', 'Other reports are being computed. Try again in a moment.'],
        [503, 'report_timeout', 'This report took too long to compute. Narrow the dates or the form version, or try again.'],
        [503, 'audit_unavailable', 'The file could not be made. Nothing was saved. Try again.'],
        [500, undefined, 'The file could not be made. Nothing was saved. Try again.']
    ])('says what went wrong after a %s %s, and saves nothing', async (status, code, text) => {
        mayExport();
        server.exportCard.mockReturnValue(refusal(status, code));
        renderPage();
        fireEvent.click(within(teamCard()).getByRole('button', { name: /^Download as CSV/ }));
        expect(await within(teamCard()).findByRole('status')).toHaveTextContent(text);
        expect(handed).toHaveLength(0);
    });

    it('is Dutch in Dutch', async () => {
        mayExport();
        await i18n.changeLanguage('nl');
        renderPage();
        expect(within(screen.getAllByRole('figure')[0]).getByRole('button', { name: /^Downloaden als CSV/ })).toBeInTheDocument();
    });

    it('finds no axe violation with the download offered', async () => {
        mayExport();
        const { container } = renderPage();
        expect(await axeViolations(container)).toEqual([]);
    });
});
