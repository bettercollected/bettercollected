import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import type { EmailAction } from '@app/store/workspaces/email-actions-api';
import type { WebhookVariable } from '@app/store/workspaces/webhooks-api';
import { axeViolations } from '@app/test/axe';

import FormEmailActionsSection, { EmailActionsSettings } from './email-actions-section';

vi.stubGlobal(
    'ResizeObserver',
    class {
        observe() {}
        unobserve() {}
        disconnect() {}
    }
);

const status = { data: { enabled: true, configured: true } as { enabled: boolean; configured: boolean } | undefined, isLoading: false };
const actionsState: { data: EmailAction[] | undefined; isLoading: boolean; isError: boolean } = { data: [], isLoading: false, isError: false };
const variablesState: { data: WebhookVariable[] | undefined; isLoading: boolean; isError: boolean } = { data: [], isLoading: false, isError: false };
const createMock = vi.fn();
const updateMock = vi.fn();
const deleteMock = vi.fn();
const testMock = vi.fn();
const previewMock = vi.fn();
vi.mock('@app/store/workspaces/email-actions-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetEmailActionsStatusQuery: () => status,
        useGetEmailActionsQuery: () => actionsState,
        useGetEmailVariablesQuery: () => variablesState,
        useGetEmailDeliveriesQuery: () => ({ data: { items: [], total: 0 }, isLoading: false, isError: false }),
        useCreateEmailActionMutation: () => [createMock, { isLoading: false }],
        useUpdateEmailActionMutation: () => [updateMock, { isLoading: false }],
        useDeleteEmailActionMutation: () => [deleteMock, { isLoading: false }],
        useSendEmailTestMutation: () => [testMock, { isLoading: false }],
        usePreviewEmailMutation: () => [previewMock, { isLoading: false }]
    };
});

let permissions = new Set<string>();
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: (p: string) => permissions.has(p), ready: true, isLoading: false }) }));
vi.mock('@app/store/forms/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        selectForm: () => ({
            formId: 'f1',
            settings: { provider: 'self' },
            fields: [
                {
                    id: 's1',
                    type: 'slide',
                    index: 0,
                    properties: {
                        fields: [
                            { id: 'age', index: 0, type: 'number', title: 'Age' },
                            { id: 'name', index: 1, type: 'short_text', title: 'Full name' }
                        ]
                    }
                }
            ]
        })
    };
});
vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', workspaceName: 'acme' }) };
});

const wrapper = ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider>;

const template = { subject: 'Hi {{name}}', body: '{{answers}}' };
const action = (over: Partial<EmailAction> = {}): EmailAction => ({
    id: 'a1',
    name: 'Notify the team',
    enabled: true,
    en: template,
    nl: template,
    fields: [{ source: 'name', key: 'name' }],
    teamRecipients: ['owner@acme.example'],
    respondentField: null,
    condition: null,
    ...over
});
const variables: WebhookVariable[] = [
    { source: 'name', label: 'Full name', type: 'short_text', supported: true },
    { source: 'mail', label: 'Email', type: 'email', supported: true },
    { source: 'upload', label: 'Document', type: 'file_upload', supported: false, reason: 'file_not_sent' }
];
const ok = (data: any) => Promise.resolve({ data });
const fail = (status: number, code?: string) => Promise.resolve({ error: { status, data: code ? { code } : undefined } });

beforeEach(() => {
    status.data = { enabled: true, configured: true };
    actionsState.data = [];
    actionsState.isError = false;
    variablesState.data = variables;
    permissions = new Set([WorkspacePermission.WORKSPACE_MANAGE, WorkspacePermission.FORM_EDIT]);
    [createMock, updateMock, deleteMock, testMock, previewMock].forEach((m) => m.mockReset());
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('who sees the email actions', () => {
    it('is hidden while the server has them off', () => {
        status.data = { enabled: false, configured: true };
        expect(render(<FormEmailActionsSection />, { wrapper }).container).toBeEmptyDOMElement();
    });

    it('is hidden from members who cannot edit the form', () => {
        permissions = new Set([WorkspacePermission.FORM_READ]);
        expect(render(<FormEmailActionsSection />, { wrapper }).container).toBeEmptyDOMElement();
    });

    it('gives owners and admins the actions and the sent mails', () => {
        render(<FormEmailActionsSection />, { wrapper });
        expect(screen.getByRole('heading', { name: 'Email' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Sent mails' })).toBeInTheDocument();
    });

    it('gives editors the sent mails only', () => {
        permissions = new Set([WorkspacePermission.FORM_EDIT]);
        render(<FormEmailActionsSection />, { wrapper });
        expect(screen.queryByTestId('email-actions-section')).not.toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Sent mails' })).toBeInTheDocument();
    });

    it('says when the server has no mail server', () => {
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured={false} />, { wrapper });
        expect(screen.getByRole('alert')).toHaveTextContent('no mail server set up');
    });
});

describe('the list', () => {
    it('shows each action with who it mails, and switches it on and off', async () => {
        actionsState.data = [action({ respondentField: 'mail', condition: { operator: 'AND', conditions: [{ fieldId: 'age', fieldType: 'number', comparison: 'GREATER_THAN', value: 1 } as any] } })];
        updateMock.mockReturnValue(ok(action({ enabled: false })));
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        const card = screen.getByTestId('email-action-a1');
        expect(card).toHaveTextContent('Notify the team');
        expect(card).toHaveTextContent('Mails 1 team address');
        expect(card).toHaveTextContent('Copy to the respondent');
        expect(card).toHaveTextContent('Runs only when conditions match');
        fireEvent.click(within(card).getByRole('switch', { name: 'Send email for Notify the team' }));
        await waitFor(() => expect(updateMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', actionId: 'a1', body: { enabled: false } }));
        expect(await screen.findByText('Notify the team is off.')).toBeInTheDocument();
    });

    it('sends a test to yourself, for the team mail and for the copy', async () => {
        actionsState.data = [action({ respondentField: 'mail' })];
        testMock.mockReturnValue(ok({ id: 'd1', actionId: 'a1', status: 'delivered', attempts: 1, event: 'test' }));
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Send a test email for Notify the team to yourself' }));
        await waitFor(() => expect(testMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', actionId: 'a1', channel: 'team' }));
        expect(await screen.findByText('A test email for Notify the team was sent to your own address, with made-up answers.')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: "Send a test of the respondent's copy of Notify the team to yourself" }));
        await waitFor(() => expect(testMock).toHaveBeenLastCalledWith({ workspaceId: 'ws1', formId: 'f1', actionId: 'a1', channel: 'respondent' }));
    });

    it('says when a test could not be sent, and when the limit is reached', async () => {
        actionsState.data = [action()];
        testMock.mockReturnValueOnce(ok({ id: 'd1', actionId: 'a1', status: 'failed', attempts: 1, event: 'test' })).mockReturnValueOnce(fail(429, 'rate_limited'));
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        const button = screen.getByRole('button', { name: 'Send a test email for Notify the team to yourself' });
        fireEvent.click(button);
        expect(await screen.findByText('The test email for Notify the team could not be sent. See the log below.')).toBeInTheDocument();
        fireEvent.click(button);
        expect(await screen.findByText('Too many test emails. Wait a while and try again.')).toBeInTheDocument();
    });

    it('deletes only after a confirmation', async () => {
        actionsState.data = [action()];
        deleteMock.mockReturnValue(ok(undefined));
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Delete the email action Notify the team' }));
        expect(deleteMock).not.toHaveBeenCalled();
        const dialog = screen.getByRole('alertdialog');
        expect(dialog).toHaveTextContent('Its log stays for 30 days');
        fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));
        await waitFor(() => expect(deleteMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', actionId: 'a1' }));
    });
});

const openAdd = () => fireEvent.click(screen.getByTestId('email-add'));
const fillBasics = () => {
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Notify' } });
    fireEvent.change(screen.getByLabelText('Team addresses'), { target: { value: 'owner@acme.example' } });
    fireEvent.click(screen.getByLabelText('Full name'));
};

describe('adding an email action', () => {
    it('starts with a template in both languages and creates it', async () => {
        createMock.mockReturnValue(ok(action()));
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        openAdd();
        expect(screen.getByLabelText('Subject')).toHaveValue('New response to {{form_title}}');
        fillBasics();
        fireEvent.click(screen.getByRole('button', { name: 'Add email action', hidden: false }));
        await waitFor(() => expect(createMock).toHaveBeenCalled());
        const body = createMock.mock.calls[0][0].body;
        expect(body).toMatchObject({ name: 'Notify', enabled: true, teamRecipients: ['owner@acme.example'], respondentField: null, condition: null, fields: [{ source: 'name', key: 'name' }] });
        expect(body.en.subject).toBe('New response to {{form_title}}');
        expect(body.nl.subject).toBe('Nieuwe inzending voor {{form_title}}');
    });

    it('refuses an address that is a name or a list, and no recipient, before sending', () => {
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        openAdd();
        fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Notify' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add email action' }));
        expect(screen.getByText('Add a team address, or choose an email question for a copy.')).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText('Team addresses'), { target: { value: 'Owner <owner@acme.example>' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add email action' }));
        expect(screen.getByText(/one plain email address per line/)).toBeInTheDocument();
        expect(createMock).not.toHaveBeenCalled();
    });

    it('refuses a placeholder that is not a ticked question, naming it', () => {
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        openAdd();
        fillBasics();
        fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Hi {{nickname}}' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add email action' }));
        expect(screen.getByText(/\{\{nickname\}\} is not one of the questions ticked above/)).toBeInTheDocument();
        expect(createMock).not.toHaveBeenCalled();
    });

    it('inserts a placeholder from the picker into the field that had the focus', () => {
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        openAdd();
        fireEvent.click(screen.getByLabelText('Full name'));
        const subject = screen.getByLabelText('Subject') as HTMLInputElement;
        fireEvent.change(subject, { target: { value: 'Hi ' } });
        subject.focus();
        subject.setSelectionRange(3, 3);
        fireEvent.focus(subject);
        fireEvent.click(screen.getByRole('button', { name: 'Insert name' }));
        expect(subject.value).toBe('Hi {{name}}');
        // no answers block for a subject: the picker offers it for the body
        expect(screen.getByRole('button', { name: 'Insert answers' })).toBeInTheDocument();
    });

    it("shows the server's preview of the template, in the language being edited", async () => {
        previewMock.mockReturnValue(ok({ subject: 'Hi Example text', body: 'Full name: Example text' }));
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        openAdd();
        fireEvent.click(screen.getByLabelText('Full name'));
        fireEvent.click(screen.getByLabelText('Dutch'));
        fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
        const preview = await screen.findByTestId('email-preview');
        await waitFor(() => expect(preview).toHaveTextContent('Hi Example text'));
        expect(preview).toHaveTextContent('Nothing was sent');
        expect(previewMock.mock.calls[0][0].body).toMatchObject({ language: 'nl', fields: [{ source: 'name', key: 'name' }] });
    });

    it('offers a copy to the respondent only from an email question', () => {
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        openAdd();
        fireEvent.click(screen.getByLabelText('Send the respondent a copy of their own answers'));
        const select = screen.getByLabelText('Email question') as HTMLSelectElement;
        expect(
            within(select)
                .getAllByRole('option')
                .map((o) => o.textContent)
        ).toEqual(['Choose a question…', 'Email']);
        expect(select.value).toBe('mail');
    });

    it('puts a refusal of the server next to what it is about', async () => {
        createMock.mockReturnValue(fail(422, 'recipient_not_allowed'));
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        openAdd();
        fillBasics();
        fireEvent.click(screen.getByRole('button', { name: 'Add email action' }));
        const message = await screen.findByText('A team address must be the address of a member of this workspace.');
        expect(screen.getByLabelText('Team addresses').getAttribute('aria-describedby')).toContain(message.id);
    });

    it('sends the condition, and refuses an unfinished one', async () => {
        createMock.mockReturnValue(ok(action()));
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        openAdd();
        fillBasics();
        fireEvent.click(screen.getByRole('switch', { name: 'Only run when' }));
        fireEvent.click(screen.getByRole('button', { name: 'Add email action' }));
        expect(createMock).not.toHaveBeenCalled();
        expect(screen.getAllByText(/Finish every condition/).length).toBeGreaterThan(0);
        fireEvent.change(screen.getByLabelText('Value'), { target: { value: '18' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add email action' }));
        await waitFor(() => expect(createMock).toHaveBeenCalled());
        expect(createMock.mock.calls[0][0].body.condition).toMatchObject({ operator: 'AND', conditions: [{ fieldId: 'age', comparison: 'IS_EQUAL', value: '18' }] });
    });
});

describe('editing and a11y', () => {
    it('edits an action with its saved values and removes a condition with null', async () => {
        actionsState.data = [action({ condition: { operator: 'AND', conditions: [{ fieldId: 'age', fieldType: 'number', comparison: 'GREATER_THAN', value: 1 } as any] } })];
        updateMock.mockReturnValue(ok(action()));
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Edit the email action Notify the team' }));
        expect(screen.getByLabelText('Team addresses')).toHaveValue('owner@acme.example');
        fireEvent.click(screen.getByRole('switch', { name: 'Only run when' }));
        fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
        await waitFor(() => expect(updateMock).toHaveBeenCalled());
        expect(updateMock.mock.calls[0][0]).toMatchObject({ actionId: 'a1', body: { condition: null, teamRecipients: ['owner@acme.example'] } });
    });

    it('is read in Dutch when the language is Dutch', async () => {
        await i18n.changeLanguage('nl');
        render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        expect(screen.getByRole('heading', { name: 'E-mail' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'E-mailactie toevoegen' })).toBeInTheDocument();
    });

    it('has no accessibility violations in the list and in the editor', async () => {
        actionsState.data = [action({ respondentField: 'mail' })];
        const { container } = render(<EmailActionsSettings workspaceId="ws1" formId="f1" configured />, { wrapper });
        expect(await axeViolations(container)).toEqual([]);
        openAdd();
        expect(await axeViolations(container)).toEqual([]);
    });
});
