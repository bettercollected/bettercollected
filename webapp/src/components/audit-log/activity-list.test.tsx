import React from 'react';

import { act, fireEvent, render as rtlRender, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuditPageDto } from '@app/models/dtos/audit-log-dto';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { store } from '@app/store/store';
import { axeViolations } from '@app/test/axe';

import { ActivityGate } from './activity-list';

const render = (ui: React.ReactElement) => rtlRender(ui, { wrapper: ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider> });

// ---- the world around the component -------------------------------------------------------------------------------

const replace = vi.fn();
let search = '';
vi.mock('next/navigation', () => ({
    useRouter: () => ({ replace, push: vi.fn() }),
    usePathname: () => '/acme/dashboard/activity',
    useSearchParams: () => new URLSearchParams(search)
}));

let permissions = new Set<string>();
const flags = { ready: true, answered: true, on: true, revisions: true };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (p: string) => permissions.has(p), ready: flags.ready, answered: flags.answered, isLoading: false, auditLogUiEnabled: flags.on, formRevisionsUiEnabled: flags.revisions })
}));
vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', workspaceName: 'acme' }) };
});

const requests: Array<{ workspaceId: string; formId?: string; query: string }> = [];
let respond: (query: string) => Promise<AuditPageDto>;
const trigger = (arg: { workspaceId: string; formId?: string; query: string }) => {
    requests.push(arg);
    return { unwrap: () => respond(arg.query) };
};
const lazy = [trigger];
vi.mock('@app/store/workspaces/audit-log-api', () => ({ useLazyGetAuditLogQuery: () => lazy }));
// the export has its own tests (export-menu.test.tsx)
vi.mock('@app/store/workspaces/audit-export', () => ({ requestAuditExport: vi.fn(), saveBlob: vi.fn() }));
// the retention setting has its own tests (retention-setting.test.tsx); here nobody can change it
vi.mock('@app/store/workspaces/audit-retention-api', () => ({ useGetAuditRetentionQuery: () => ({ data: undefined }), useSetAuditRetentionMutation: () => [vi.fn(), { isLoading: false }] }));

// ---- data (made up) ------------------------------------------------------------------------------------------------

const labels: AuditPageDto['labels'] = {
    members: { u_sanne: { status: 'member', name: 'Sanne de Vries' }, u_pim: { status: 'member', name: 'Pim Jansen' }, u_left: { status: 'former' } },
    forms: { f_join: { status: 'available', title: 'Join the volunteers' }, f_contact: { status: 'available', title: 'Contact form' }, f_gone: { status: 'gone' } },
    teams: { g_intake: { status: 'available', name: 'Intake' } }
};
const today = new Date();
const at = (hours: number) => new Date(today.getFullYear(), today.getMonth(), today.getDate(), hours, 5).toISOString();
const older = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 5, 9, 2).toISOString();

const FIRST: AuditPageDto = {
    entries: [
        { id: 'e1', event: 'access_grant_added', area: 'access', at: at(10), actorId: 'u_sanne', groupId: 'g_intake', formId: 'f_join', grantRole: 'REVIEWER', grantExport: true },
        { id: 'e2', event: 'response_staff_edit', area: 'responses', at: at(9), actorId: 'u_pim', formId: 'f_contact', responseId: 'r_77', revision: 2, sessionId: 'sess_abc' },
        { id: 'e3', event: 'member_removed', area: 'members', at: older, actorId: 'u_sanne', targetUserId: 'u_left' }
    ],
    nextCursor: 'cursor-2',
    labels,
    retentionDays: 365
};
const SECOND: AuditPageDto = {
    entries: [
        { id: 'e4', event: 'form_deleted', area: 'forms', at: older, actorId: 'u_sanne', formId: 'f_gone' },
        { id: 'e5', event: 'webhook_created', area: 'forms', at: older, actorId: 'u_pim' }
    ],
    nextCursor: null,
    labels,
    retentionDays: 365
};

const OWNER = [WorkspacePermission.AUDIT_READ, WorkspacePermission.RESPONSE_READ, WorkspacePermission.FORM_READ, WorkspacePermission.FORM_EDIT];
const PRIVACY_OFFICER = [WorkspacePermission.AUDIT_READ, WorkspacePermission.FORM_READ, WorkspacePermission.PRIVACY_MANAGE];

beforeEach(() => {
    search = '';
    requests.length = 0;
    replace.mockReset();
    permissions = new Set(OWNER);
    Object.assign(flags, { ready: true, answered: true, on: true, revisions: true });
    respond = async (query) => (new URLSearchParams(query).get('cursor') ? SECOND : FIRST);
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

const sentence = (text: string | RegExp) => screen.getByText((_, el) => el?.tagName === 'P' && (typeof text === 'string' ? el.textContent === text : text.test(el.textContent ?? '')));

const show = async (formId?: string) => {
    render(<ActivityGate formId={formId} />);
    await screen.findByTestId('activity-list');
    await waitFor(() => expect(screen.queryByText('Loading activity')).not.toBeInTheDocument());
};

// ---- the tests -------------------------------------------------------------------------------------------------------

describe('the workspace Activity page', () => {
    it('offers the export of the filters on screen, on the workspace page and on a form page', async () => {
        search = 'area=access&who=u_sanne';
        await show();
        expect(screen.getByRole('button', { name: /Export/ })).toBeInTheDocument();
    });

    it('lists one sentence per entry under day headings, newest first, with the retention figure', async () => {
        await show();
        expect(screen.getByRole('heading', { level: 1, name: 'Activity' })).toBeInTheDocument();
        expect(screen.getByText(/Entries are kept for 12 months\./)).toBeInTheDocument();
        const items = screen.getAllByRole('listitem').filter((li) => li.querySelector('time'));
        expect(items).toHaveLength(3);
        expect(items[0]).toHaveTextContent('Sanne de Vries gave the team Intake Reviewer access to Join the volunteers, including export of responses.');
        expect(items[1]).toHaveTextContent('Pim Jansen edited answers of a response of Contact form (change 2).');
        expect(items[2]).toHaveTextContent('Sanne de Vries removed a member who has left from the workspace.');
        expect(screen.getByRole('heading', { level: 2, name: 'Today' })).toBeInTheDocument();
        expect(items[0].querySelector('time')).toHaveAttribute('datetime', at(10));
        // the area is text, not colour only
        expect(within(items[0]).getByText('Access')).toBeInTheDocument();
    });

    it('names the people and forms in bold and never shows the id of a person, form or team', async () => {
        await show();
        const first = screen.getAllByRole('listitem').filter((li) => li.querySelector('time'))[0];
        expect([...first.querySelectorAll('strong')].map((s) => s.textContent)).toEqual(['Sanne de Vries', 'Intake', 'Join the volunteers']);
        for (const id of ['u_sanne', 'f_join', 'g_intake', 'u_left', 'cursor-2']) expect(document.body.textContent).not.toContain(id);
    });

    it('is worded in Dutch when the language is Dutch', async () => {
        await i18n.changeLanguage('nl');
        await show();
        expect(screen.getAllByRole('listitem')[0]).toHaveTextContent('Sanne de Vries gaf het team Intake toegang als Beoordelaar tot Join the volunteers, inclusief het exporteren van reacties.');
        expect(screen.getByText(/Regels worden 12 maanden bewaard\./)).toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 2, name: 'Vandaag' })).toBeInTheDocument();
    });

    it('asks the server for the default view: everything but the break-glass requests', async () => {
        await show();
        const query = new URLSearchParams(requests[0].query);
        expect(requests[0]).toMatchObject({ workspaceId: 'ws1', formId: undefined });
        expect(query.getAll('area')).toEqual(['access', 'members', 'forms', 'responses', 'api_keys', 'integrations']);
        expect(query.getAll('event')).not.toContain('sso_break_glass_request');
        expect(screen.getByText('Break-glass requests are hidden.')).toBeInTheDocument();
    });

    it('shows the break-glass requests when asked: the button chooses the Security area in the address', async () => {
        await show();
        fireEvent.click(screen.getByRole('button', { name: 'Show them' }));
        expect(replace).toHaveBeenCalledWith('/acme/dashboard/activity?area=security', { scroll: false });
    });

    it('has no axe violations', async () => {
        await show();
        expect(await axeViolations(document.body, { page: false })).toEqual([]);
    });
});

describe('the filters, kept in the address', () => {
    it('writes a chosen type, person, form and date into the address', async () => {
        await show();
        fireEvent.click(screen.getByRole('checkbox', { name: 'Access' }));
        expect(replace).toHaveBeenLastCalledWith('/acme/dashboard/activity?area=access', { scroll: false });
        fireEvent.change(screen.getByLabelText('Person'), { target: { value: 'u_pim' } });
        expect(replace).toHaveBeenLastCalledWith('/acme/dashboard/activity?who=u_pim', { scroll: false });
        fireEvent.change(screen.getByLabelText('Form'), { target: { value: 'f_contact' } });
        expect(replace).toHaveBeenLastCalledWith('/acme/dashboard/activity?form=f_contact', { scroll: false });
        fireEvent.change(screen.getByLabelText('From (UTC)'), { target: { value: '2026-10-01' } });
        expect(replace).toHaveBeenLastCalledWith('/acme/dashboard/activity?from=2026-10-01', { scroll: false });
    });

    it('offers the people and forms the log has shown so far', async () => {
        await show();
        expect(within(screen.getByLabelText('Person')).getAllByRole('option').map((o) => o.textContent)).toEqual(['Anyone', 'Pim Jansen', 'Sanne de Vries']);
        expect(within(screen.getByLabelText('Form')).getAllByRole('option').map((o) => o.textContent)).toEqual(['All forms', 'Contact form', 'Join the volunteers']);
    });

    it('reads the address: it filters the request and shows removable chips', async () => {
        search = 'area=access&who=u_pim&about=1&form=f_contact&from=2026-10-01&to=2026-10-31';
        await show();
        const query = new URLSearchParams(requests[0].query);
        expect(query.getAll('area')).toEqual(['access']);
        expect(query.get('involving')).toBe('u_pim');
        expect(query.get('form_id')).toBe('f_contact');
        expect(query.get('from')).toBe('2026-10-01T00:00:00Z');
        expect(query.get('to')).toBe('2026-10-31T23:59:59.999Z');
        const chips = within(screen.getByRole('list', { name: 'Active filters' }));
        expect(chips.getByRole('button', { name: 'Remove filter: Type: Access' })).toBeInTheDocument();
        fireEvent.click(chips.getByRole('button', { name: /Remove filter: Form: / }));
        expect(replace).toHaveBeenLastCalledWith('/acme/dashboard/activity?area=access&who=u_pim&about=1&from=2026-10-01&to=2026-10-31', { scroll: false });
    });

    it('names the date chips by their UTC day, whatever the time zone of the viewer', async () => {
        const zone = process.env.TZ;
        process.env.TZ = 'America/Los_Angeles';
        try {
            search = 'from=2026-10-01&to=2026-10-31';
            await show();
            const chips = within(screen.getByRole('list', { name: 'Active filters' }));
            expect(chips.getByRole('button', { name: 'Remove filter: From Thursday, 1 October 2026' })).toBeInTheDocument();
            expect(chips.getByRole('button', { name: 'Remove filter: To Saturday, 31 October 2026' })).toBeInTheDocument();
        } finally {
            if (zone === undefined) delete process.env.TZ;
            else process.env.TZ = zone;
        }
    });

    it('clears every filter', async () => {
        search = 'area=access&form=f_contact';
        await show();
        fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
        expect(replace).toHaveBeenLastCalledWith('/acme/dashboard/activity', { scroll: false });
    });

    it('labels every control and groups the filters as a search', async () => {
        await show();
        const search = screen.getByRole('search', { name: 'Filters' });
        for (const label of ['Person', 'Form', 'From (UTC)', 'To (UTC)']) expect(within(search).getByLabelText(label)).toBeInTheDocument();
        expect(within(search).getByRole('group', { name: 'Type' })).toBeInTheDocument();
    });

    it('does not ask for a range that ends before it starts', async () => {
        search = 'from=2026-10-31&to=2026-10-01';
        render(<ActivityGate />);
        expect(await screen.findByRole('alert')).toHaveTextContent('The start date is after the end date.');
        expect(requests).toHaveLength(0);
    });
});

describe('older entries', () => {
    it('appends the next page with the cursor, announces it politely and keeps the focus where it was', async () => {
        await show();
        const button = screen.getByRole('button', { name: 'Show older entries' });
        button.focus();
        fireEvent.click(button);
        await waitFor(() => expect(screen.getAllByRole('listitem').filter((li) => li.querySelector('time'))).toHaveLength(5));
        expect(new URLSearchParams(requests[1].query).get('cursor')).toBe('cursor-2');
        // an unknown kind from a newer server reads as the neutral sentence, with the rest still in place
        expect(screen.getByText('An action was recorded.')).toBeInTheDocument();
        expect(sentence('Sanne de Vries deleted an item that no longer exists.')).toBeInTheDocument();
        const announcer = screen.getByTestId('activity-announcer');
        expect(announcer).toHaveAttribute('aria-live', 'polite');
        expect(announcer).toHaveTextContent('2 more entries loaded');
        // the last page: the same button stays (and keeps the focus), saying there is nothing older
        expect(document.activeElement).toBe(button);
        expect(button).toHaveTextContent('No older entries');
        expect(button).toHaveAttribute('aria-disabled', 'true');
    });

    it('has no button when everything fits on the first page', async () => {
        respond = async () => ({ ...FIRST, nextCursor: null });
        await show();
        expect(screen.queryByRole('button', { name: /older entries/ })).not.toBeInTheDocument();
    });

    it('says so when older entries cannot be loaded, and keeps what is shown', async () => {
        await show();
        respond = async () => {
            throw new Error('down');
        };
        fireEvent.click(screen.getByRole('button', { name: 'Show older entries' }));
        expect(await screen.findByRole('alert')).toHaveTextContent('Older entries could not be loaded.');
        expect(screen.getAllByRole('listitem').filter((li) => li.querySelector('time'))).toHaveLength(3);
    });

    it('starts again from the first page when a filter changes', async () => {
        const { rerender } = render(<ActivityGate />);
        await screen.findByRole('button', { name: 'Show older entries' });
        fireEvent.click(screen.getByRole('button', { name: 'Show older entries' }));
        await screen.findByText('An action was recorded.');
        search = 'area=members';
        rerender(<ActivityGate />);
        await waitFor(() => expect(screen.queryByText('An action was recorded.')).not.toBeInTheDocument());
        expect(new URLSearchParams(requests[requests.length - 1].query).get('cursor')).toBeNull();
        expect(new URLSearchParams(requests[requests.length - 1].query).getAll('area')).toEqual(['members']);
    });
});

describe('empty, loading and error states', () => {
    it('says nothing has been recorded yet', async () => {
        respond = async () => ({ entries: [], nextCursor: null, labels: {}, retentionDays: 365 });
        await show();
        expect(screen.getByText(/Nothing has been recorded yet/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument();
    });

    it('says no entry matches the filters, with a way out', async () => {
        search = 'area=access';
        respond = async () => ({ entries: [], nextCursor: null, labels: {}, retentionDays: 365 });
        await show();
        expect(screen.getByText('No entries match these filters.')).toBeInTheDocument();
        const clear = screen.getAllByRole('button', { name: 'Clear filters' });
        fireEvent.click(clear[clear.length - 1]);
        expect(replace).toHaveBeenLastCalledWith('/acme/dashboard/activity', { scroll: false });
    });

    it('shows a loading line first', async () => {
        let release: (page: AuditPageDto) => void = () => undefined;
        respond = () => new Promise((resolve) => (release = resolve));
        render(<ActivityGate />);
        expect(await screen.findByText('Loading activity')).toBeInTheDocument();
        await act(async () => release(FIRST));
        expect(screen.queryByText('Loading activity')).not.toBeInTheDocument();
    });

    it('shows an inline alert with Retry, and loads again on Retry', async () => {
        respond = async () => {
            throw new Error('down');
        };
        render(<ActivityGate />);
        const alert = await screen.findByRole('alert');
        expect(alert).toHaveTextContent('The activity could not be loaded.');
        respond = async () => FIRST;
        fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
        expect(await screen.findByText((_, el) => el?.tagName === 'P' && /gave the team Intake/.test(el.textContent ?? ''))).toBeInTheDocument();
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
});

describe('what the server decides', () => {
    it('shows a session id and a response link only when the server sent them (an Owner)', async () => {
        await show();
        expect(screen.getByText('Session sess_abc')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /Open the response from/ })).toHaveAttribute('href', '/acme/dashboard/forms/f_contact/responses/r_77');
    });

    it('renders no session id and no response link when the server left them out (a Privacy officer)', async () => {
        permissions = new Set(PRIVACY_OFFICER);
        respond = async () => ({ ...FIRST, entries: FIRST.entries.map(({ sessionId, responseId, ...rest }) => rest) });
        await show();
        expect(screen.getAllByRole('listitem').filter((li) => li.querySelector('time'))).toHaveLength(3);
        expect(screen.queryByText(/Session/)).not.toBeInTheDocument();
        expect(screen.queryByRole('link', { name: /Open/ })).not.toBeInTheDocument();
        expect(document.body.textContent).not.toContain('sess_abc');
        expect(document.body.textContent).not.toContain('r_77');
    });

    it('does not work out a link from the permissions: no response id from the server, no link, even for response.read', async () => {
        respond = async () => ({ ...FIRST, entries: FIRST.entries.map(({ responseId, ...rest }) => rest) });
        await show();
        expect(screen.queryByRole('link', { name: /Open/ })).not.toBeInTheDocument();
    });
});

describe('the switch and the permission', () => {
    it('asks for nothing and draws nothing while the server has the page off, and goes back to the forms list', async () => {
        flags.on = false;
        render(<ActivityGate />);
        expect(screen.queryByTestId('activity-list')).not.toBeInTheDocument();
        expect(requests).toHaveLength(0);
        await waitFor(() => expect(replace).toHaveBeenCalledWith('/acme/dashboard/forms'));
    });

    it('says so, with a way to try again, when the permissions request failed: never a blank page', () => {
        flags.answered = false;
        const dispatch = vi.spyOn(store, 'dispatch');
        render(<ActivityGate />);
        expect(screen.getByRole('alert')).toHaveTextContent('Your access to this page could not be checked.');
        expect(requests).toHaveLength(0);
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
        expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: expect.stringContaining('invalidateTags') }));
        dispatch.mockRestore();
    });

    it('asks for nothing until the permissions have arrived', () => {
        flags.ready = false;
        flags.answered = false;
        render(<ActivityGate />);
        expect(screen.queryByTestId('activity-list')).not.toBeInTheDocument();
        expect(requests).toHaveLength(0);
        expect(replace).not.toHaveBeenCalled();
    });

    it('says so, and asks for nothing, without audit.read', () => {
        permissions = new Set([WorkspacePermission.FORM_READ, WorkspacePermission.FORM_EDIT]);
        render(<ActivityGate />);
        expect(screen.getByText('You do not have access to the activity of this workspace.')).toBeInTheDocument();
        expect(requests).toHaveLength(0);
    });
});

describe("a form's Activity", () => {
    it("asks the form's route, has no Form filter, says \"this form\" and links to the workspace list", async () => {
        search = 'form=f_contact';
        respond = async () => ({ entries: [{ id: 'e1', event: 'access_mode_changed', area: 'access', at: at(10), actorId: 'u_sanne', formId: 'f_join', accessMode: 'restricted' }], nextCursor: null, labels, retentionDays: 365 });
        await show('f_join');
        expect(requests[0]).toMatchObject({ workspaceId: 'ws1', formId: 'f_join' });
        // the form comes from the route, never from the address or the query
        expect(new URLSearchParams(requests[0].query).get('form_id')).toBeNull();
        expect(screen.queryByLabelText('Form')).not.toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 2, name: 'Activity' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 3, name: 'Today' })).toBeInTheDocument();
        expect(sentence('Sanne de Vries made this form restricted: only people with access can open it.')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'See all activity in this workspace' })).toHaveAttribute('href', '/acme/dashboard/activity?form=f_join');
        expect(screen.queryByText('Break-glass requests are hidden.')).not.toBeInTheDocument();
    });

    it('links the form\'s other histories by what the person may open', async () => {
        await show('f_join');
        expect(screen.getByRole('link', { name: 'Versions' })).toHaveAttribute('href', '/acme/dashboard/forms/f_join/versions');
        expect(screen.getByRole('link', { name: 'Deliveries' })).toHaveAttribute('href', '/acme/dashboard/forms/f_join/settings/automations');
        expect(screen.getByRole('link', { name: 'Responses' })).toHaveAttribute('href', '/acme/dashboard/forms/f_join/responses');
    });

    it('shows a Privacy officer the entries without a link into the responses', async () => {
        permissions = new Set(PRIVACY_OFFICER);
        await show('f_join');
        expect(screen.getByRole('link', { name: 'Versions' })).toBeInTheDocument();
        expect(screen.queryByRole('link', { name: 'Deliveries' })).not.toBeInTheDocument();
        expect(screen.queryByRole('link', { name: 'Responses' })).not.toBeInTheDocument();
    });
});
