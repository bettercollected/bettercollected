import React from 'react';

import { readFileSync, readdirSync } from 'fs';
import { join } from 'path';

import { fireEvent, render, screen, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';
import { ANONYMOUS_RESPONSE, FORM, RESPONSE } from '@app/test/response-fixtures';

import ResponsePage from './response-page';

// The "server": what the submission endpoint answers for the response asked for.
const server: { result: any; calls: any[]; refetch: ReturnType<typeof vi.fn> } = { result: {}, calls: [], refetch: vi.fn() };
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWorkspaceSubmissionQuery: (arg: any, options: any) => {
            server.calls.push({ arg, options });
            return { refetch: server.refetch, isFetching: false, ...server.result };
        },
        useUpdateInternalAnswersMutation: () => [vi.fn(), { isLoading: false }],
        usePostRespondentFeedbackMutation: () => [vi.fn(), { isLoading: false }]
    };
});

const access: { permissions: string[] } = { permissions: [] };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => access.permissions.includes(permission), permissions: new Set(access.permissions), isLoading: false, ready: true })
}));

const neighbours: { value: { previousId?: string; nextId?: string } } = { value: {} };
vi.mock('@app/utils/response-list-memory', () => ({ rememberedNeighbours: () => neighbours.value }));

const openModal = vi.fn();
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal, closeModal: vi.fn() }) }));

const loaded = (response: any = RESPONSE, extra: Record<string, unknown> = {}) => ({ currentData: { response, form: FORM, internalFields: [], feedback: null, ...extra }, isError: false });
const renderPage = (responseId = 'resp-1', formId = 'form-1') =>
    render(
        <ReduxProvider store={store}>
            <ResponsePage formId={formId} responseId={responseId} />
        </ReduxProvider>
    );

beforeEach(() => {
    server.calls = [];
    server.refetch = vi.fn();
    server.result = loaded();
    access.permissions = [WorkspacePermission.RESPONSE_READ];
    openModal.mockReset();
    neighbours.value = {};
    store.dispatch(setWorkspace({ id: 'workspace-1', workspaceName: 'acme' } as any));
    store.dispatch(setAuth({ id: 'me', email: 'staff@example.com', roles: [] } as any));
    document.title = '';
});

describe('the response page', () => {
    it('asks for this response of this workspace, and always asks again when opened', () => {
        renderPage();
        expect(server.calls[0].arg).toEqual({ workspace_id: 'workspace-1', submission_id: 'resp-1' });
        expect(server.calls[0].options).toMatchObject({ refetchOnMountOrArgChange: true });
    });

    it('says who answered, when (with the zone) and the start of the receipt number', () => {
        renderPage();
        const details = screen.getByRole('region', { name: 'Response details' });
        expect(within(details).getByText('anna@example.com')).toBeInTheDocument();
        expect(within(details).getByText(/^30 October 2026(,| at) \d{2}:\d{2}:\d{2} \S+$/)).toBeInTheDocument();
        expect(within(details).getByText('#0a1b2c3d…')).toBeInTheDocument();
    });

    it('never shows the full receipt number (it is a bearer token): not in the page, a tooltip or a link', () => {
        const { container } = renderPage();
        expect(container.textContent).not.toContain('4222');
        expect(container.textContent).not.toContain('444455556666');
        expect(container.innerHTML).not.toContain('0a1b2c3d-1111');
        expect(container.querySelector('[title*="0a1b2c3d"]')).toBeNull();
        container.querySelectorAll('a[href]').forEach((link) => expect(link.getAttribute('href')).not.toContain('0a1b2c3d'));
    });

    it('shows the Anonymous mark and no email for an anonymous response', () => {
        server.result = loaded(ANONYMOUS_RESPONSE);
        renderPage('resp-2');
        const details = screen.getByRole('region', { name: 'Response details' });
        expect(within(details).getByText('Anonymous')).toBeInTheDocument();
        // (the email question's own answer is an answer, not the responder)
        expect(within(details).queryByText('anna@example.com')).toBeNull();
    });

    it('titles the tab "Response · <form title>", never the responder email or an answer', () => {
        renderPage();
        expect(document.title).toBe('Response · Summer meeting registration');
        expect(document.title).not.toContain('anna@example.com');
        expect(document.title).not.toContain('Anna');
    });

    it('goes back to the list with a real link', () => {
        renderPage();
        const back = screen.getByRole('link', { name: /Responses/ });
        expect(back).toHaveAttribute('href', '/acme/dashboard/forms/form-1/responses');
    });

    it('draws the response like the form below the details, and the unreadable notice once at the top', () => {
        server.result = loaded({ ...RESPONSE, answers: {}, unreadableFields: ['answers'] });
        renderPage();
        expect(screen.getAllByText('This response could not be decrypted')).toHaveLength(1);
        expect(screen.getAllByText('Could not be decrypted').length).toBeGreaterThan(5);
        expect(screen.queryByText('No answer')).toBeNull();
        expect(screen.getByRole('heading', { level: 1, name: 'Summer meeting registration' })).toBeInTheDocument();
    });

    it('shows a pending deletion request on the response', () => {
        server.result = loaded({ ...RESPONSE, deletionStatus: 'pending' });
        renderPage();
        expect(screen.getByText('Requested by the responder')).toBeInTheDocument();
    });

    describe('delete', () => {
        it('is offered to staff who may delete, goes through the existing confirmation and then back to the list', () => {
            access.permissions = [WorkspacePermission.RESPONSE_READ, WorkspacePermission.RESPONSE_DELETE];
            renderPage();
            fireEvent.click(screen.getByRole('button', { name: 'Delete response' }));
            expect(openModal).toHaveBeenCalledWith('DELETE_RESPONSE', { workspace: expect.objectContaining({ id: 'workspace-1' }), formId: 'form-1', responseId: 'resp-1', navigateTo: '/acme/dashboard/forms/form-1/responses' });
        });

        it('is not offered without response.delete', () => {
            renderPage();
            expect(screen.queryByRole('button', { name: 'Delete response' })).toBeNull();
        });
    });

    describe('previous and next', () => {
        // which neighbours the remembered list pages give is tested in utils/response-list-memory.test.ts
        it('leaves them out when the staff member did not come from the list (nothing cached)', () => {
            neighbours.value = {};
            renderPage();
            expect(screen.queryByRole('link', { name: 'Previous response' })).toBeNull();
            expect(screen.queryByRole('link', { name: 'Next response' })).toBeNull();
        });

        it('links to the neighbours the list gives', () => {
            neighbours.value = { previousId: 'x1', nextId: 'x3' };
            renderPage();
            expect(screen.getByRole('link', { name: 'Previous response' })).toHaveAttribute('href', '/acme/dashboard/forms/form-1/responses/x1');
            expect(screen.getByRole('link', { name: 'Next response' })).toHaveAttribute('href', '/acme/dashboard/forms/form-1/responses/x3');
        });

        it('disables the one that does not exist (the first or last response of the list)', () => {
            neighbours.value = { nextId: 'x3' };
            renderPage();
            expect(screen.getByRole('button', { name: 'Previous response' })).toBeDisabled();
            expect(screen.getByRole('link', { name: 'Next response' })).toBeInTheDocument();
        });
    });

    describe('states', () => {
        it('shows a loading state, never "No answer"', () => {
            server.result = { currentData: undefined, isError: false, isFetching: true };
            renderPage();
            expect(screen.getByRole('status')).toHaveTextContent('Loading response…');
            expect(screen.queryByText('No answer')).toBeNull();
        });

        it('says there is no permission for a 403, without a Retry', () => {
            server.result = { currentData: undefined, isError: true, error: { status: 403, data: 'Forbidden' } };
            renderPage();
            expect(screen.getByRole('alert')).toHaveTextContent('You do not have access to this response');
            expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
            expect(screen.getByRole('link', { name: 'Back to responses' })).toHaveAttribute('href', '/acme/dashboard/forms/form-1/responses');
            expect(screen.queryByText('No answer')).toBeNull();
            expect(document.title).toBe('Response');
        });

        it('says it was not found for a 404, without a Retry', () => {
            server.result = { currentData: undefined, isError: true, error: { status: 404 } };
            renderPage();
            expect(screen.getByRole('alert')).toHaveTextContent('This response was not found');
            expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
        });

        it('says it was not found for a response of another form', () => {
            server.result = loaded({ ...RESPONSE, formId: 'other-form' }, {});
            server.result.currentData.form = { ...FORM, formId: 'other-form' };
            renderPage('resp-1', 'form-1');
            expect(screen.getByRole('alert')).toHaveTextContent('This response was not found');
            expect(screen.queryByText('Anna Example')).toBeNull();
        });

        it('offers Retry for any other failure and asks again with it', () => {
            server.result = { currentData: undefined, isError: true, error: { status: 500 } };
            renderPage();
            expect(screen.getByRole('alert')).toHaveTextContent('Could not load this response');
            fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
            expect(server.refetch).toHaveBeenCalledTimes(1);
            expect(screen.queryByText('No answer')).toBeNull();
        });

        it('treats a network failure like any other failure', () => {
            server.result = { currentData: undefined, isError: true, error: { status: 'FETCH_ERROR', error: 'Failed to fetch' } };
            renderPage();
            expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
        });
    });

    describe('the staff-only parts', () => {
        it('shows the respondent feedback panel and the internal fields panel, outside the form look', () => {
            server.result = loaded(RESPONSE, {
                feedback: { entries: [], status: null },
                internalFields: [{ id: 'note', index: 0, type: 'short_text', title: 'Office note', internal: true, properties: { fields: [] } }]
            });
            const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
            const { container } = renderPage();
            // (two panels side by side must not share a React key)
            expect(errors).not.toHaveBeenCalled();
            errors.mockRestore();
            const staff = screen.getByRole('region', { name: 'For the team only' });
            expect(container.querySelector('[data-response-form]')!.contains(staff)).toBe(false);
            expect(within(staff).getByText(/Office note/)).toBeInTheDocument();
        });

        it('shows neither for a response with no feedback and no internal fields', () => {
            renderPage();
            expect(screen.queryByRole('region', { name: 'For the team only' })).toBeNull();
        });
    });

    it('prints without the toolbar and the staff panels', () => {
        access.permissions = [WorkspacePermission.RESPONSE_READ, WorkspacePermission.RESPONSE_DELETE];
        server.result = loaded(RESPONSE, { internalFields: [{ id: 'note', index: 0, type: 'short_text', title: 'Office note', internal: true, properties: { fields: [] } }] });
        const { container } = renderPage();
        expect(container.querySelector('header')!.className).toContain('print:hidden');
        expect(screen.getByRole('region', { name: 'For the team only' }).className).toContain('print:hidden');
    });

    it('has no accessibility violation on the whole page (WCAG A/AA and page structure)', async () => {
        access.permissions = [WorkspacePermission.RESPONSE_READ, WorkspacePermission.RESPONSE_DELETE];
        renderPage();
        expect(await axeViolations(document, { page: true })).toEqual([]);
    });

    it('has no accessibility violation in the failure states', async () => {
        server.result = { currentData: undefined, isError: true, error: { status: 500 } };
        renderPage();
        expect(await axeViolations(document, { page: true })).toEqual([]);
    });
});

describe('analytics and storage', () => {
    // The page code never touches the analytics tracker or the browser's storage: the only
    // pageviews Umami gets are the public form's (lib/analytics/umami.ts), auto-tracking is
    // off in app/layout.tsx, and nothing decrypted is kept in the browser.
    const here = __dirname;
    const sources = readdirSync(here)
        .filter((file) => /\.tsx?$/.test(file) && !/\.test\./.test(file))
        .map((file) => [file, readFileSync(join(here, file), 'utf8')] as const);

    it('has source files to check', () => {
        expect(sources.length).toBeGreaterThanOrEqual(3);
    });

    it.each(sources)('%s has no analytics call and no browser storage', (_file, source) => {
        expect(source).not.toMatch(/umami|trackCanonicalFormView|@app\/lib\/analytics/i);
        expect(source).not.toMatch(/localStorage|sessionStorage|indexedDB|caches\./);
    });

    it('keeps Umami auto-track off for every route, this one included', () => {
        const layout = readFileSync(join(here, '../../app/layout.tsx'), 'utf8');
        expect(layout).toContain('data-auto-track="false"');
    });
});
