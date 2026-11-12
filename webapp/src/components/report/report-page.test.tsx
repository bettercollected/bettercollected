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
import { ReportCardDef, ReportDefinition, ReportResult, cardsParam, parseCardsParam } from '@app/utils/report';

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
    asked: Array<{ definition: ReportDefinition; skip: boolean }>;
    refetch: ReturnType<typeof vi.fn>;
    refetchFields: ReturnType<typeof vi.fn>;
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
        return { data: options.skip || server.queryError ? undefined : server.result(args.definition), error: server.queryError, isError: !!server.queryError, isFetching: server.fetching, refetch: server.refetch };
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
    server.asked = [];
    server.refetch = vi.fn();
    server.refetchFields = vi.fn();
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
        server.queryError = { status: 413, data: { code: 'too_many_rows', count: 25000, max: 20000 } };
        renderPage();
        const alert = screen.getByRole('alert');
        expect(alert).toHaveTextContent('This selection has 25000 responses. Narrow the dates to at most 20000 to see the figures.');
        fireEvent.click(within(alert).getByRole('button', { name: 'Only the last 30 days' }));
        expect(nav.pushes.at(-1)).toMatch(/from=\d{4}-\d{2}-\d{2}/);
    });

    it('too many rows: narrows to the current version', () => {
        server.queryError = { status: 413, data: { code: 'too_many_rows', count: 25000, max: 20000 } };
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
        const status = () => screen.getAllByRole('status').find((node) => node.getAttribute('aria-live') === 'polite') as HTMLElement;
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
        server.queryError = { status: 413, data: { code: 'too_many_rows', count: 25000, max: 20000 } };
        renderPage();
        expect(screen.getByRole('alert')).toHaveTextContent('Deze selectie heeft 25000 reacties. Beperk de periode tot ten hoogste 20000 om de cijfers te zien.');
        expect(screen.getByRole('button', { name: 'Alleen de laatste 30 dagen' })).toBeInTheDocument();
    });
});

describe('axe', () => {
    it('finds no violation in the page, the refusal or the empty state', async () => {
        const { container, unmount } = renderPage();
        expect(await axeViolations(container)).toEqual([]);
        unmount();
        server.queryError = { status: 413, data: { code: 'too_many_rows', count: 25000, max: 20000 } };
        const refused = renderPage();
        expect(await axeViolations(refused.container)).toEqual([]);
        refused.unmount();
        server.queryError = undefined;
        server.result = (definition) => figures(definition, 0);
        const empty = renderPage();
        expect(await axeViolations(empty.container)).toEqual([]);
    });
});

