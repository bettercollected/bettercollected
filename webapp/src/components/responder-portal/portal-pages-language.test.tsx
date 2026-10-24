// The respondent portal's lists and a submission's own pages are in the
// respondent's language (?lang=, else the browser's) and marked with it, and
// each page has one h1 with headings in order. The team's preview of the
// portal on their dashboard keeps the app's language.
// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { render, screen, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import WorkspaceResponsesTabContent from '@app/components/dashboard/workspace-responses-tab-content';
import RequestForDeletionView from '@app/components/submission-request-for-deletion/submission-request-for-deletion';
import '@app/shared/hocs/i18n-provider';
import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';
import { utcToLocalDateIn, utcToLocalDateTimeIn } from '@app/utils/date-utils';

import ResponderPortalLayoutClient from './responder-portal-layout-client';
import { SubmissionProvider } from './submission-context';
import SubmissionLayoutClient from './submission-layout-client';
import SubmissionSettingsContent from './submission-settings-context';

const nav = vi.hoisted(() => ({ pathname: '/acme/forms' }));

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => nav.pathname,
    useSearchParams: () => new URLSearchParams(window.location.search)
}));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn(), closeModal: vi.fn() }) }));
// The organisation's own feedback panel (for members) is not part of these pages' text.
vi.mock('@Components/form/respondent-feedback-panel', () => ({ default: () => null }));

// One slide holding `count` questions (a v2 form).
const fields = (count: number) => [{ id: 's1', type: 'slide', index: 0, properties: { fields: Array.from({ length: count }, (_, index) => ({ id: `q${index}`, type: 'short_text', title: `Q${index}`, index })) } }];
const intake = { formId: 'f1', title: 'Intake', builderVersion: 'v2', fields: fields(3), settings: { customUrl: 'intake', pinned: true, purpose: 'To plan the season.' } };
const survey = { formId: 'f2', title: '', builderVersion: 'v2', fields: fields(1), settings: { customUrl: 'survey' } };
const submission = {
    responseId: 'r1',
    formTitle: 'Intake',
    submissionUuid: 'AB12',
    createdAt: '2026-10-01T10:00:00',
    updatedAt: '2026-10-01T10:00:00',
    provider: 'self',
    dataOwnerIdentifier: null
};

vi.mock('@app/store/workspaces/api', async (importOriginal) => ({
    ...(await importOriginal<typeof import('@app/store/workspaces/api')>()),
    useGetWorkspaceFormsQuery: (query: { pinned_only?: boolean }) => ({ isLoading: false, isError: false, data: query.pinned_only ? { items: [intake], total: 1 } : { items: [intake, survey], total: 2 } }),
    useLazySearchWorkspaceFormsQuery: () => [vi.fn()],
    // Signed out the list isn't fetched.
    useGetWorkspaceSubmissionsQuery: (_query: unknown, options?: { skip?: boolean }) => (options?.skip ? { isLoading: false, data: undefined } : { isLoading: false, data: { items: [submission], total: 1 } })
}));

const workspace = { id: 'w1', workspaceName: 'acme', title: 'Buurthuis De Linde' } as any;
const at = (url: string) => window.history.replaceState(null, '', url);
const signIn = () => store.dispatch(setAuth({ id: 'u1', email: 'someone@example.com', isLoading: false }));
const signOut = () => store.dispatch(setAuth({ id: '', email: '', isLoading: false }));

/** The page's headings as "h<level> <text>", in document order. */
const outline = () => Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map((h) => `${h.tagName.toLowerCase()} ${h.textContent?.trim()}`);
/** No heading is more than one level deeper than the one before it. */
const levelsInOrder = (headings: string[]) => headings.every((heading, index) => index === 0 || Number(heading[1]) <= Number(headings[index - 1][1]) + 1);

beforeEach(() => {
    store.dispatch(setWorkspace(workspace));
    (window as any).PUBLIC_CONFIG = { FORM_DOMAIN: window.location.host };
});
afterEach(() => {
    signOut();
    at('/');
    nav.pathname = '/acme/forms';
});

const renderPortal = (children: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <ResponderPortalLayoutClient hasCustomDomain={false}>{children}</ResponderPortalLayoutClient>
        </ReduxProvider>
    );

describe('the portal forms page', () => {
    it('has one h1, the workspace, and its headings in order', async () => {
        signOut();
        at('/acme/forms?lang=nl');
        renderPortal(<WorkspaceFormsTabContent workspace={workspace} />);
        // Once every part has picked up the respondent's language.
        await screen.findByRole('heading', { level: 2, name: 'Alle formulieren (2)' });
        await screen.findByRole('heading', { level: 2, name: 'Uitgelichte formulieren (1)' });
        await screen.findByRole('heading', { level: 3, name: 'Formulier zonder titel' });
        const headings = outline();
        expect(headings.filter((h) => h.startsWith('h1'))).toEqual(['h1 Buurthuis De Linde']);
        expect(headings[0]).toBe('h1 Buurthuis De Linde');
        expect(levelsInOrder(headings)).toBe(true);
        expect(headings).toContain('h2 Uitgelichte formulieren (1)');
        expect(headings).toContain('h2 Alle formulieren (2)');
        expect(await axeViolations(document, { page: true })).toEqual([]);
    });

    it('describes each form card in Dutch and keeps ?lang on its link', async () => {
        at('/acme/forms?lang=nl');
        renderPortal(<WorkspaceFormsTabContent workspace={workspace} />);
        const allForms = (await screen.findByRole('heading', { level: 2, name: 'Alle formulieren (2)' })).closest('section')!;
        const intakeLink = within(allForms).getByRole('link', { name: /Intake/ });
        expect(intakeLink).toHaveAttribute('href', '/acme/forms/intake?lang=nl');
        expect((await within(intakeLink).findByText('3 vragen')).closest('[lang]')).toHaveAttribute('lang', 'nl');
        expect(within(intakeLink).getByText('Uitgelicht')).toBeInTheDocument();
        expect(within(intakeLink).getByText('(opent in een nieuw tabblad)')).toBeInTheDocument();
        const untitled = within(allForms).getByRole('heading', { level: 3, name: 'Formulier zonder titel' });
        expect(untitled).toHaveAttribute('lang', 'nl');
        expect(within(untitled.closest('a')!).getByText('1 vraag')).toBeInTheDocument();
    });

    it('keeps a screen-reader heading over the list when nothing is pinned', async () => {
        at('/acme/forms?lang=en');
        renderPortal(<WorkspaceFormsTabContent workspace={workspace} />);
        expect(await screen.findByRole('heading', { level: 2, name: 'Pinned forms (1)' })).toBeInTheDocument();
        expect(screen.getByText('3 questions')).toBeInTheDocument();
    });
});

describe('the portal submission lists', () => {
    it('signed out, invites the respondent to find their submissions, in Dutch', async () => {
        signOut();
        at('/acme/my-submissions?lang=nl');
        nav.pathname = '/acme/my-submissions';
        renderPortal(<WorkspaceResponsesTabContent workspace={workspace} audience="respondent" />);
        expect(await screen.findByRole('heading', { level: 2, name: 'Je inzendingen vinden' })).toBeInTheDocument();
        expect(screen.getAllByRole('button', { name: 'E-mailadres bevestigen' }).length).toBeGreaterThan(0);
        expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
        expect(levelsInOrder(outline())).toBe(true);
        expect(await axeViolations(document, { page: true })).toEqual([]);
    });

    it('signed in, lists each receipt in Dutch, as an h3 under the tab heading', async () => {
        signIn();
        at('/acme/my-submissions?lang=nl');
        nav.pathname = '/acme/my-submissions';
        renderPortal(<WorkspaceResponsesTabContent workspace={workspace} audience="respondent" />);
        await screen.findByRole('heading', { level: 2, name: 'Mijn inzendingen' });
        const card = (await screen.findByRole('heading', { level: 3, name: 'Intake' })).closest('a')!;
        await within(card).findByText('Anoniem');
        expect(card).toHaveAttribute('href', '/acme/submissions/r1/form?lang=nl');
        expect(within(card).getByText(`Ingezonden: ${utcToLocalDateTimeIn(submission.createdAt, 'nl')}`)).toBeInTheDocument();
        expect(within(card).getByText('Anoniem')).toHaveAttribute('title', 'Ingezonden zonder je naam of e-mailadres erbij');
        expect(screen.getByRole('heading', { level: 2, name: 'Mijn inzendingen' })).toBeInTheDocument();
        expect(screen.getByText(/Anonieme inzendingen zijn niet gekoppeld aan je account/)).toBeInTheDocument();
        expect(levelsInOrder(outline())).toBe(true);
        expect(await axeViolations(document, { page: true })).toEqual([]);
    });

    it("stays in the app's language on the team's dashboard", async () => {
        signOut();
        at('/acme/dashboard?lang=nl');
        render(
            <ReduxProvider store={store}>
                <WorkspaceResponsesTabContent workspace={workspace} />
            </ReduxProvider>
        );
        expect(await screen.findByRole('heading', { level: 2, name: 'Find your submissions' })).toBeInTheDocument();
    });
});

const renderSubmission = (response: Record<string, unknown>, path: 'form' | 'settings' = 'settings', workspaceName = 'acme') => {
    nav.pathname = `/acme/submissions/r1/${path}`;
    return render(
        <ReduxProvider store={store}>
            <SubmissionProvider value={{ data: { form: { formId: 'f1', title: 'Intake' }, response: { ...submission, ...response } }, isLoading: false, isError: false, handleRequestForDeletion: vi.fn(), hasCustomDomain: false, workspaceName, submissionId: 'r1', isUUID: false }}>
                <SubmissionLayoutClient>
                    <SubmissionSettingsContent />
                </SubmissionLayoutClient>
            </SubmissionProvider>
        </ReduxProvider>
    );
};

describe('a submission’s own pages', () => {
    it('are in Dutch, marked so, with the form title as the one h1', async () => {
        at('/acme/submissions/r1/settings?lang=nl');
        renderSubmission({});
        expect(await screen.findByRole('link', { name: 'Mijn inzendingen' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 1, name: 'Intake' })).toBeInTheDocument();
        await screen.findByRole('button', { name: 'Verwijdering aanvragen' });
        expect(document.documentElement).toHaveAttribute('lang', 'nl');
        expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
        expect(screen.getByRole('link', { name: 'Mijn inzendingen' })).toHaveAttribute('href', '/acme/my-submissions?lang=nl');
        const tabs = screen.getByRole('navigation', { name: 'Je inzending' });
        expect(within(tabs).getByRole('link', { name: 'Mijn antwoorden' })).toHaveAttribute('href', '/acme/submissions/r1/form?lang=nl');
        expect(within(tabs).getByRole('link', { name: 'Privacy en verwijderen' })).toHaveAttribute('aria-current', 'page');
        expect(screen.getByText(`Ingezonden: ${utcToLocalDateTimeIn(submission.createdAt, 'nl')}`)).toBeInTheDocument();
        expect(screen.getByText(/Deze antwoorden zijn van jou/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Verwijdering aanvragen' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Mogelijk gemaakt door bettercollected' })).toHaveAttribute('lang', 'nl');
        expect(await axeViolations(document, { page: true })).toEqual([]);
    });

    it('show a pending deletion request as pending', async () => {
        at('/acme/submissions/r1/settings?lang=nl');
        renderSubmission({ deletionStatus: 'pending' });
        expect(await screen.findByText('Verwijdering aangevraagd · In behandeling')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Verwijdering aanvragen' })).toBeNull();
    });

    it('never show a declined request as pending or deleted', async () => {
        at('/acme/submissions/r1/settings?lang=en');
        renderSubmission({ deletionStatus: 'declined', declineReason: 'legal_obligation' });
        expect(await screen.findAllByText('Not deleted: the organisation must keep it by law')).toHaveLength(2);
        expect(screen.queryByText(/Pending/)).toBeNull();
        expect(screen.queryByRole('button', { name: 'Request deletion' })).toBeNull();
    });

    it('ask to confirm a deletion request in Dutch', async () => {
        at('/acme/submissions/r1/settings?lang=nl');
        render(<RequestForDeletionView handleRequestForDeletion={vi.fn()} />);
        expect(await screen.findByText('De organisatie vragen om deze antwoorden te verwijderen?')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Annuleren' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Verwijdering aanvragen' }).closest('[lang]')).toHaveAttribute('lang', 'nl');
    });
});

describe('dates in the respondent’s language', () => {
    it('writes the month out in English or Dutch', () => {
        expect(utcToLocalDateIn('2026-10-01T10:00:00', 'nl')).toMatch(/oktober 2026$/);
        expect(utcToLocalDateIn('2026-10-01T10:00:00', 'en')).toMatch(/October 2026$/);
        expect(utcToLocalDateTimeIn(undefined, 'nl')).toBe('');
    });
});

// A workspace handle comes from the route and the API: whatever it holds,
// every portal link stays on this site (no protocol-relative "//host" href).
describe('portal links with a hostile workspace handle', () => {
    const HOSTILE = ['//evil.com', '/evil.com', '%2Fevil.com', '%2F', 'javascript:alert(1)'];
    const linksStayOnSite = () => {
        const hrefs = Array.from(document.querySelectorAll('a[href]'))
            .map((a) => a.getAttribute('href')!)
            // the fixed outside links (credits, footer, default terms and privacy)
            .filter((href) => !/^https:\/\/(bettercollected\.com|sireto\.com)(\/|$)/.test(href));
        expect(hrefs.length).toBeGreaterThan(0);
        for (const href of hrefs) {
            expect(href, href).toMatch(/^\/(?![/\\])/);
            expect(new URL(href, 'https://forms.example').origin, href).toBe('https://forms.example');
        }
    };

    it.each(HOSTILE)('the portal, its form cards and receipts for %j', async (workspaceName) => {
        signIn();
        store.dispatch(setWorkspace({ ...workspace, workspaceName }));
        at('/x/forms?lang=en');
        const { unmount } = renderPortal(<WorkspaceFormsTabContent workspace={{ ...workspace, workspaceName }} />);
        await screen.findByRole('heading', { level: 3, name: 'Intake' });
        linksStayOnSite();
        unmount();
        renderPortal(<WorkspaceResponsesTabContent workspace={{ ...workspace, workspaceName }} audience="respondent" />);
        await screen.findByRole('heading', { level: 3, name: 'Intake' });
        linksStayOnSite();
    });

    it.each(HOSTILE)('a submission page for %j', async (workspaceName) => {
        at('/x/submissions/r1/settings?lang=en');
        renderSubmission({}, 'settings', workspaceName);
        await screen.findByRole('heading', { level: 1, name: 'Intake' });
        linksStayOnSite();
    });
});
