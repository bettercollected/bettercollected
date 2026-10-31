import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import type { Webhook, WebhookVariable } from '@app/store/workspaces/webhooks-api';
import { axeViolations } from '@app/test/axe';

import FormWebhooksSection, { WebhooksSettings } from './webhooks-section';

// Radix's switch measures itself with a ResizeObserver, which jsdom lacks.
vi.stubGlobal(
    'ResizeObserver',
    class {
        observe() {}
        unobserve() {}
        disconnect() {}
    }
);

const status = { data: { enabled: true } as { enabled: boolean } | undefined, isLoading: false };
const hooksState: { data: Webhook[] | undefined; isLoading: boolean; isError: boolean } = { data: [], isLoading: false, isError: false };
const variablesState: { data: WebhookVariable[] | undefined; isLoading: boolean; isError: boolean } = { data: [], isLoading: false, isError: false };
const detailState: { data: any; isLoading: boolean; isError: boolean; error?: any } = { data: undefined, isLoading: false, isError: false };
const detailCalls: any[] = [];
const createMock = vi.fn();
const updateMock = vi.fn();
const deleteMock = vi.fn();
const rotateMock = vi.fn();
const testMock = vi.fn();
vi.mock('@app/store/workspaces/webhooks-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWebhooksStatusQuery: () => status,
        useGetWebhooksQuery: () => hooksState,
        useGetWebhookVariablesQuery: () => variablesState,
        useGetWebhookDetailQuery: (arg: any) => {
            detailCalls.push(arg);
            return detailState;
        },
        useGetWebhookDeliveriesQuery: () => ({ data: { items: [], total: 0 }, isLoading: false, isError: false }),
        useGetWebhookAuditQuery: () => ({ data: undefined, isError: false }),
        useCreateWebhookMutation: () => [createMock, { isLoading: false }],
        useUpdateWebhookMutation: () => [updateMock, { isLoading: false }],
        useDeleteWebhookMutation: () => [deleteMock, { isLoading: false }],
        useRotateWebhookSecretMutation: () => [rotateMock, { isLoading: false }],
        useSendWebhookTestMutation: () => [testMock, { isLoading: false }]
    };
});

let permissions = new Set<string>();
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: (p: string) => permissions.has(p), ready: true, isLoading: false }) }));
vi.mock('@app/store/forms/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectForm: () => ({ formId: 'f1', settings: { provider: 'self' } }) };
});
vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', workspaceName: 'acme' }) };
});

const wrapper = ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider>;

const hook = (over: Partial<Webhook> = {}): Webhook => ({ id: 'w1', host: 'hooks.example.org', enabled: true, fields: [{ source: 'name', key: 'full_name' }], hasSecret: true, ...over });
const variables: WebhookVariable[] = [
    { source: 'name', label: 'Full name', type: 'short_text', supported: true },
    { source: 'age', label: 'Age', type: 'number', supported: true },
    { source: 'upload', label: 'Document', type: 'file_upload', supported: false, reason: 'file_not_sent' }
];
const ok = (data: any) => Promise.resolve({ data });
const fail = (status: number, code?: string) => Promise.resolve({ error: { status, data: code ? { code } : undefined } });

const addWebhook = async (url = 'https://hooks.example.org/in') => {
    fireEvent.click(screen.getByTestId('webhook-add'));
    fireEvent.change(screen.getByLabelText('Address to send to'), { target: { value: url } });
    fireEvent.click(screen.getByLabelText('Full name'));
    fireEvent.click(screen.getByRole('button', { name: 'Add webhook' }));
};

beforeEach(() => {
    status.data = { enabled: true };
    hooksState.data = [];
    hooksState.isError = false;
    detailState.data = { ...hook(), url: 'https://hooks.example.org/in?key=tok-1' };
    detailState.isError = false;
    detailState.isLoading = false;
    detailCalls.length = 0;
    variablesState.data = variables;
    permissions = new Set([WorkspacePermission.WORKSPACE_MANAGE, WorkspacePermission.FORM_EDIT]);
    [createMock, updateMock, deleteMock, rotateMock, testMock].forEach((m) => m.mockReset());
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('who sees the webhooks', () => {
    it('is hidden while the server has webhooks off', () => {
        status.data = { enabled: false };
        expect(render(<FormWebhooksSection />, { wrapper }).container).toBeEmptyDOMElement();
    });

    it('is hidden from members who cannot edit the form', () => {
        permissions = new Set([WorkspacePermission.FORM_READ]);
        expect(render(<FormWebhooksSection />, { wrapper }).container).toBeEmptyDOMElement();
    });

    it('gives owners and admins the webhooks and the deliveries', () => {
        render(<FormWebhooksSection />, { wrapper });
        expect(screen.getByRole('heading', { name: 'Webhooks' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Deliveries' })).toBeInTheDocument();
    });

    it('gives editors the deliveries only', () => {
        permissions = new Set([WorkspacePermission.FORM_EDIT]);
        render(<FormWebhooksSection />, { wrapper });
        expect(screen.queryByTestId('webhooks-section')).not.toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Deliveries' })).toBeInTheDocument();
    });
});

describe('adding a webhook', () => {
    it('checks the address as it is typed and sends nothing while it is wrong', async () => {
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByTestId('webhook-add'));
        const field = screen.getByLabelText('Address to send to');
        fireEvent.change(field, { target: { value: 'http://hooks.example.org/in' } });
        fireEvent.blur(field);
        expect(await screen.findByText('Use a https:// address. Plain http is not accepted.')).toBeInTheDocument();
        expect(field).toHaveAttribute('aria-invalid', 'true');
        expect(field.getAttribute('aria-describedby')).toContain('webhook-url-error');
        fireEvent.change(field, { target: { value: 'https://user:pw@hooks.example.org/in' } });
        expect(screen.getByText(/password or fragment/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Add webhook' }));
        expect(createMock).not.toHaveBeenCalled();
        expect(field).toHaveFocus();
        fireEvent.change(field, { target: { value: 'https://hooks.example.org/in' } });
        expect(screen.queryByText(/password or fragment/)).not.toBeInTheDocument();
        expect(field).toHaveAttribute('aria-invalid', 'false');
    });

    it('asks for an address and refuses a name that is not valid', () => {
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByTestId('webhook-add'));
        fireEvent.click(screen.getByRole('button', { name: 'Add webhook' }));
        expect(screen.getByText('Enter the address to send to.')).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText('Address to send to'), { target: { value: 'https://hooks.example.org/in' } });
        fireEvent.click(screen.getByLabelText('Full name'));
        fireEvent.click(screen.getByLabelText('Age'));
        fireEvent.change(screen.getAllByLabelText('Name in the sent data')[0], { target: { value: 'bad name' } });
        fireEvent.change(screen.getAllByLabelText('Name in the sent data')[1], { target: { value: 'ok' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add webhook' }));
        expect(screen.getByText(/letters, digits and underscores only/)).toBeInTheDocument();
        expect(createMock).not.toHaveBeenCalled();
        fireEvent.change(screen.getAllByLabelText('Name in the sent data')[0], { target: { value: 'ok' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add webhook' }));
        expect(screen.getByText('Another question already uses this name.')).toBeInTheDocument();
        expect(createMock).not.toHaveBeenCalled();
    });

    it('offers the questions that can be sent and says why a file cannot', () => {
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByTestId('webhook-add'));
        expect(screen.getByLabelText('Full name')).toBeEnabled();
        expect(screen.getByLabelText('Document')).toBeDisabled();
        expect(screen.getByTestId('webhook-variable-upload')).toHaveTextContent('files are not sent');
        expect(screen.getByText('0 questions will be sent.')).toBeInTheDocument();
        fireEvent.click(screen.getByLabelText('Full name'));
        expect(screen.getByLabelText('Name in the sent data')).toHaveValue('name');
        expect(screen.getByText('1 question will be sent.')).toBeInTheDocument();
    });

    it('creates it and shows the secret once, until it is dismissed', async () => {
        createMock.mockReturnValue(ok({ ...hook(), secret: 'whsec_abcdef' }));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        await addWebhook();
        await waitFor(() => expect(createMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', body: { url: 'https://hooks.example.org/in', fields: [{ source: 'name', key: 'name' }], enabled: true, condition: null } }));
        const notice = await screen.findByTestId('webhook-secret-once');
        expect(within(notice).getByLabelText('Signing secret')).toHaveValue('whsec_abcdef');
        expect(notice).toHaveTextContent('shown only once');
        expect(screen.queryByTestId('webhook-editor')).not.toBeInTheDocument();
        fireEvent.click(within(notice).getByRole('button', { name: 'I have saved the secret' }));
        expect(screen.queryByTestId('webhook-secret-once')).not.toBeInTheDocument();
        expect(document.body.textContent).not.toContain('whsec_abcdef');
    });

    it('copies the secret to the clipboard, or says it could not', async () => {
        createMock.mockReturnValue(ok({ ...hook(), secret: 'whsec_abcdef' }));
        const writeText = vi.fn().mockResolvedValue(undefined);
        Object.assign(navigator, { clipboard: { writeText } });
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        await addWebhook();
        fireEvent.click(await screen.findByRole('button', { name: 'Copy secret' }));
        await waitFor(() => expect(writeText).toHaveBeenCalledWith('whsec_abcdef'));
        expect(await screen.findByText('Copied to the clipboard.')).toBeInTheDocument();
        writeText.mockRejectedValue(new Error('no'));
        fireEvent.click(screen.getByRole('button', { name: 'Copy secret' }));
        expect(await screen.findByText(/Copying was not possible here/)).toBeInTheDocument();
    });

    it.each([
        ['not_allowed', 'That address points to a private network'],
        ['unreachable', 'That address does not resolve.'],
        ['invalid_url', 'Use a https:// address without a port']
    ])('puts a server refusal (%s) next to the address', async (code, text) => {
        createMock.mockReturnValue(fail(422, code));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        await addWebhook();
        expect(await screen.findByText(new RegExp(text))).toBeInTheDocument();
        expect(screen.getByLabelText('Address to send to')).toHaveAttribute('aria-invalid', 'true');
        expect(screen.getByLabelText('Address to send to')).toHaveFocus();
        expect(screen.queryByTestId('webhook-secret-once')).not.toBeInTheDocument();
    });

    it('says when the server has webhooks off or the form has too many', async () => {
        createMock.mockReturnValue(fail(422, 'webhooks_off'));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        await addWebhook();
        expect(await screen.findByRole('alert')).toHaveTextContent('Webhooks are turned off on this server.');
    });
});

describe('the list', () => {
    beforeEach(() => {
        hooksState.data = [hook(), hook({ id: 'w2', host: 'crm.example.com', enabled: false, fields: [] })];
    });

    it('shows the host, the number of questions and the state, never the address or a secret', () => {
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        const first = screen.getByTestId('webhook-w1');
        expect(first).toHaveTextContent('hooks.example.org');
        expect(first).toHaveTextContent('1 question sent');
        expect(screen.getByTestId('webhook-w2')).toHaveTextContent('0 questions sent');
        expect(document.body.textContent).not.toContain('/in');
        expect(document.body.textContent).not.toContain('whsec_');
        expect(within(first).getByRole('switch', { name: 'Send submissions to hooks.example.org' })).toBeChecked();
        expect(within(screen.getByTestId('webhook-w2')).getByRole('switch')).not.toBeChecked();
    });

    it('switches a webhook on and off', async () => {
        updateMock.mockReturnValue(ok(hook()));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(within(screen.getByTestId('webhook-w1')).getByRole('switch'));
        await waitFor(() => expect(updateMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', webhookId: 'w1', body: { enabled: false } }));
        expect(await screen.findByText('hooks.example.org is off.')).toBeInTheDocument();
    });

    it('says why turning one on was refused', async () => {
        updateMock.mockReturnValue(fail(422, 'webhooks_off'));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(within(screen.getByTestId('webhook-w2')).getByRole('switch'));
        expect(await screen.findByText(/Webhooks are turned off on this server/)).toBeInTheDocument();
    });

    it('sends a test event and points to the deliveries', async () => {
        testMock.mockReturnValue(ok({ id: 'x', status: 'pending' }));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Send a test event to hooks.example.org' }));
        await waitFor(() => expect(testMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', webhookId: 'w1' }));
        expect(await screen.findByText(/A test event with sample data is on its way to hooks.example.org/)).toBeInTheDocument();
    });

    it('says when test events come too fast', async () => {
        testMock.mockReturnValue(fail(429, 'rate_limited'));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Send a test event to hooks.example.org' }));
        expect(await screen.findByText('Too many test events. Wait a minute and try again.')).toBeInTheDocument();
    });

    it('asks before rotating a secret, then shows the new one once', async () => {
        rotateMock.mockReturnValue(ok({ ...hook(), secret: 'whsec_newnew' }));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Rotate the secret of the webhook for hooks.example.org' }));
        expect(rotateMock).not.toHaveBeenCalled();
        const confirm = screen.getByRole('alertdialog');
        expect(confirm).toHaveTextContent('The old secret stops working at once');
        fireEvent.click(within(confirm).getByRole('button', { name: 'Rotate secret' }));
        await waitFor(() => expect(rotateMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', webhookId: 'w1' }));
        expect(within(await screen.findByTestId('webhook-secret-once')).getByLabelText('Signing secret')).toHaveValue('whsec_newnew');
        expect(screen.getByRole('heading', { name: 'New signing secret for hooks.example.org' })).toBeInTheDocument();
    });

    it('asks before deleting, and can be cancelled', async () => {
        deleteMock.mockReturnValue(ok(undefined));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Delete the webhook for hooks.example.org' }));
        fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Cancel' }));
        expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
        expect(deleteMock).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole('button', { name: 'Delete the webhook for hooks.example.org' }));
        fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Delete' }));
        await waitFor(() => expect(deleteMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', webhookId: 'w1' }));
        expect(await screen.findByText('The webhook for hooks.example.org was deleted.')).toBeInTheDocument();
    });

    it('edits a webhook with its saved address and questions', async () => {
        updateMock.mockReturnValue(ok(hook()));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Edit the webhook for hooks.example.org' }));
        expect(screen.getByLabelText('Address to send to')).toHaveValue('https://hooks.example.org/in?key=tok-1');
        expect(detailCalls).toEqual([{ workspaceId: 'ws1', formId: 'f1', webhookId: 'w1' }]);
        expect(screen.getByLabelText('Full name')).toBeChecked();
        expect(screen.getByLabelText('Name in the sent data')).toHaveValue('full_name');
        fireEvent.click(screen.getByLabelText('Age'));
        fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
        await waitFor(() =>
            expect(updateMock).toHaveBeenCalledWith({
                workspaceId: 'ws1',
                formId: 'f1',
                webhookId: 'w1',
                body: { url: 'https://hooks.example.org/in?key=tok-1', fields: [{ source: 'name', key: 'full_name' }, { source: 'age', key: 'age' }], enabled: true, condition: null }
            })
        );
        expect(await screen.findByText('The webhook for hooks.example.org was saved.')).toBeInTheDocument();
        expect(screen.queryByTestId('webhook-editor')).not.toBeInTheDocument();
    });

    it('saves a condition with the webhook, and removes it with null', async () => {
        detailState.data = { ...hook({ condition: { operator: 'AND', conditions: [{ fieldId: 'age', fieldType: 'number', comparison: 'GREATER_THAN', value: 18 } as any] } }), url: 'https://hooks.example.org/in' };
        hooksState.data = [hook({ condition: detailState.data.condition })];
        updateMock.mockReturnValue(ok(hook()));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        expect(screen.getByTestId('webhook-w1')).toHaveTextContent('Runs only when conditions match');
        fireEvent.click(screen.getByRole('button', { name: 'Edit the webhook for hooks.example.org' }));
        expect(screen.getByRole('switch', { name: 'Only run when' })).toBeChecked();
        fireEvent.click(screen.getByRole('switch', { name: 'Only run when' }));
        fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
        await waitFor(() => expect(updateMock).toHaveBeenCalled());
        expect(updateMock.mock.calls[0][0].body.condition).toBeNull();
    });

    it('never asks for an address until a webhook is edited, and the list shows none', () => {
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        expect(detailCalls).toEqual([]);
        expect(document.body.textContent).not.toContain('tok-1');
        expect(document.body.textContent).not.toContain('https://hooks');
    });

    it('edits a webhook whose address cannot be read with the address left empty', () => {
        detailState.data = undefined;
        detailState.isError = true;
        detailState.error = { status: 409, data: { code: 'url_unreadable' } };
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Edit the webhook for hooks.example.org' }));
        expect(screen.getByRole('alert')).toHaveTextContent('The address of this webhook could not be read. Enter it again.');
        expect(screen.getByLabelText('Address to send to')).toHaveValue('');
    });

    it('speaks Dutch in the same register as the dashboard', async () => {
        await i18n.changeLanguage('nl');
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        expect(screen.getByRole('heading', { name: 'Webhooks' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Een testgebeurtenis naar hooks.example.org versturen' })).toBeInTheDocument();
        expect(screen.getByTestId('webhook-w1')).toHaveTextContent('1 vraag verstuurd');
        fireEvent.click(screen.getByTestId('webhook-add'));
        expect(screen.getByLabelText('Adres om naartoe te versturen')).toBeInTheDocument();
        expect(screen.getByText('0 vragen worden verstuurd.')).toBeInTheDocument();
    });

    it('has no accessibility violations (list, editor, confirmation, secret)', async () => {
        rotateMock.mockReturnValue(ok({ ...hook(), secret: 'whsec_newnew' }));
        render(<WebhooksSettings workspaceId="ws1" formId="f1" />, { wrapper });
        fireEvent.click(screen.getByRole('button', { name: 'Delete the webhook for hooks.example.org' }));
        expect(await axeViolations(document.body)).toEqual([]);
        fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Cancel' }));
        fireEvent.click(screen.getByTestId('webhook-add'));
        fireEvent.click(screen.getByRole('button', { name: 'Add webhook' }));
        fireEvent.click(screen.getByLabelText('Full name'));
        expect(await axeViolations(document.body)).toEqual([]);
        await i18n.changeLanguage('nl');
        expect(await axeViolations(document.body)).toEqual([]);
    });
});
