import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import type { RegistrationService } from '@app/store/workspaces/registration-api';
import { axeViolations } from '@app/test/axe';
import { ERROR_CODES, TEST_CODES, serviceErrorField } from '@app/utils/registration';

import enBuilder from '../../../public/locales/en/builder.json';
import nlBuilder from '../../../public/locales/nl/builder.json';
import ServicesSection from './services-section';

const en = enBuilder.REGISTRATION as any;
const nl = nlBuilder.REGISTRATION as any;

const queryState: { data: RegistrationService[] | undefined; isLoading: boolean; isError: boolean; refetch: () => void } = { data: [], isLoading: false, isError: false, refetch: vi.fn() };
const createMock = vi.fn();
const updateMock = vi.fn();
const deleteMock = vi.fn();
const testMock = vi.fn();
const resetMock = vi.fn();
vi.mock('@app/store/workspaces/registration-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetRegistrationServicesQuery: () => queryState,
        useCreateRegistrationServiceMutation: () => [createMock, { isLoading: false, reset: resetMock }],
        useUpdateRegistrationServiceMutation: () => [updateMock, { isLoading: false, reset: resetMock }],
        useDeleteRegistrationServiceMutation: () => [deleteMock, { isLoading: false }],
        useTestRegistrationServiceMutation: () => [testMock, { isLoading: false }]
    };
});

const toastMock = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: toastMock }) }));
vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', workspaceName: 'acme', title: 'Acme Health' }) };
});

const service = (overrides: Partial<RegistrationService> = {}): RegistrationService => ({
    id: 's1',
    name: 'Cases',
    kind: 'generic_json',
    baseUrl: 'https://cases.example.org/api',
    auth: 'header',
    authName: 'X-Api-Key',
    hasSecret: true,
    secretSetAt: '2026-10-20T09:00:00Z',
    organisationName: 'Example Organisation',
    ...overrides
});

const renderSection = () => render(<ServicesSection />, { wrapper: ({ children }) => <ReduxProvider store={store}>{children}</ReduxProvider> });

beforeEach(() => {
    queryState.data = [service()];
    queryState.isLoading = false;
    queryState.isError = false;
    createMock.mockReset();
    updateMock.mockReset();
    deleteMock.mockReset();
    testMock.mockReset();
    resetMock.mockReset();
    toastMock.mockReset();
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

const fillNew = (secret = 's3cret-value') => {
    fireEvent.change(screen.getByLabelText(en.DIALOG.NAME), { target: { value: 'Cases' } });
    fireEvent.change(screen.getByLabelText(en.DIALOG.ADDRESS), { target: { value: 'https://cases.example.org' } });
    fireEvent.change(screen.getByLabelText(en.DIALOG.AUTH), { target: { value: 'header' } });
    fireEvent.change(screen.getByLabelText(en.DIALOG.AUTH_NAME_HEADER), { target: { value: 'X-Api-Key' } });
    fireEvent.change(screen.getByLabelText(en.DIALOG.SECRET_HEADER), { target: { value: secret } });
};

describe('Case systems list', () => {
    it('shows the service as text and says a secret is set, never the secret', () => {
        // Even a response that wrongly carried the secret must not reach the page.
        queryState.data = [{ ...service(), secret: 'LEAK-123', secretSealed: 'LEAK-456' } as any];
        const { container } = renderSection();
        const card = screen.getByTestId('registration-service-s1');
        expect(within(card).getByText('Cases')).toBeInTheDocument();
        expect(within(card).getByText('https://cases.example.org/api')).toBeInTheDocument();
        expect(within(card).getByText('Example Organisation')).toBeInTheDocument();
        expect(card).toHaveTextContent(/Set on .+2026.*It is never shown/);
        expect(container.innerHTML).not.toMatch(/LEAK-/);
        expect(container.querySelectorAll('input')).toHaveLength(0);
    });

    it('renders a hostile organisation name and service name as text', () => {
        queryState.data = [service({ name: '<img src=x onerror=alert(1)>', organisationName: '<b>Acme</b>' })];
        const { container } = renderSection();
        expect(container.querySelector('img')).toBeNull();
        expect(container.querySelector('b')).toBeNull();
        expect(screen.getByText('<b>Acme</b>')).toBeInTheDocument();
        expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    });

    it('shows an empty state and an error with a way to try again', () => {
        queryState.data = [];
        const { unmount } = renderSection();
        expect(screen.getByText(en.SERVICES.EMPTY_TITLE)).toBeInTheDocument();
        unmount();
        queryState.data = undefined;
        queryState.isError = true;
        renderSection();
        expect(screen.getByRole('alert')).toHaveTextContent(en.SERVICES.LOAD_ERROR);
        fireEvent.click(screen.getByRole('button', { name: en.TRY_AGAIN }));
        expect(queryState.refetch).toHaveBeenCalled();
    });

    it('warns that a test creates a record at the destination', () => {
        renderSection();
        expect(screen.getByText(en.SERVICES.TEST_WARNING)).toBeInTheDocument();
        expect(screen.getByText(en.NOTICE)).toBeInTheDocument();
    });
});

describe('Add and edit', () => {
    it('adds a service: the secret goes in the request once and is gone from the form afterwards', async () => {
        queryState.data = [];
        createMock.mockResolvedValue({ data: service() });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.ADD }));
        // the organisation name starts as the workspace's, and is plain text in a field
        expect(screen.getByLabelText(en.DIALOG.ORGANISATION)).toHaveValue('Acme Health');
        fillNew();
        expect(screen.getByLabelText(en.DIALOG.SECRET_HEADER)).toHaveAttribute('type', 'password');
        fireEvent.click(screen.getByRole('button', { name: en.DIALOG.SAVE }));
        await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
        expect(createMock).toHaveBeenCalledWith({
            workspaceId: 'ws1',
            body: { name: 'Cases', baseUrl: 'https://cases.example.org', auth: 'header', organisationName: 'Acme Health', authName: 'X-Api-Key', secret: 's3cret-value' }
        });
        await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
        // the request, secret included, is dropped from the query cache
        expect(resetMock).toHaveBeenCalled();
        // reopened, nothing remembers it
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.ADD }));
        fireEvent.change(screen.getByLabelText(en.DIALOG.AUTH), { target: { value: 'header' } });
        expect(screen.getByLabelText(en.DIALOG.SECRET_HEADER)).toHaveValue('');
    });

    it('does not send anything while required fields are empty, and moves focus to the first one', async () => {
        queryState.data = [];
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.ADD }));
        fireEvent.change(screen.getByLabelText(en.DIALOG.ORGANISATION), { target: { value: '' } });
        fireEvent.click(screen.getByRole('button', { name: en.DIALOG.SAVE }));
        expect(createMock).not.toHaveBeenCalled();
        const name = screen.getByLabelText(en.DIALOG.NAME);
        expect(name).toHaveAttribute('aria-invalid', 'true');
        expect(name).toHaveAccessibleDescription(expect.stringContaining(en.DIALOG.REQUIRED));
        await waitFor(() => expect(name).toHaveFocus());
    });

    it('edits without ever prefilling the secret: "a secret is set" and a Replace action', () => {
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.EDIT_NAMED.replace('{{name}}', 'Cases') }));
        const stored = screen.getByTestId('registration-secret-stored');
        expect(stored).toHaveTextContent(/A secret is set since .+2026/);
        expect(screen.queryByLabelText(en.DIALOG.SECRET_HEADER)).toBeNull();
        fireEvent.click(within(stored).getByRole('button', { name: en.DIALOG.SECRET_REPLACE }));
        const field = screen.getByLabelText(en.DIALOG.SECRET_HEADER);
        expect(field).toHaveValue('');
        expect(field).toHaveAttribute('type', 'password');
    });

    it('asks for the secret again when the address changes, and patches only what changed', async () => {
        updateMock.mockResolvedValue({ data: service() });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.EDIT_NAMED.replace('{{name}}', 'Cases') }));
        fireEvent.change(screen.getByLabelText(en.DIALOG.ADDRESS), { target: { value: 'https://other.example.org' } });
        const secret = screen.getByLabelText(en.DIALOG.SECRET_HEADER);
        expect(secret).toHaveAccessibleDescription(en.DIALOG.SECRET_AGAIN);
        fireEvent.click(screen.getByRole('button', { name: en.DIALOG.SAVE }));
        expect(updateMock).not.toHaveBeenCalled();
        expect(secret).toHaveAttribute('aria-invalid', 'true');
        fireEvent.change(secret, { target: { value: 'again-1' } });
        fireEvent.click(screen.getByRole('button', { name: en.DIALOG.SAVE }));
        await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1));
        expect(updateMock).toHaveBeenCalledWith({ workspaceId: 'ws1', serviceId: 's1', body: { baseUrl: 'https://other.example.org', secret: 'again-1' } });
    });

    it('a rename alone does not send a secret', async () => {
        updateMock.mockResolvedValue({ data: service() });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.EDIT_NAMED.replace('{{name}}', 'Cases') }));
        fireEvent.change(screen.getByLabelText(en.DIALOG.NAME), { target: { value: 'Cases 2' } });
        fireEvent.click(screen.getByRole('button', { name: en.DIALOG.SAVE }));
        await waitFor(() => expect(updateMock).toHaveBeenCalled());
        expect(updateMock.mock.calls[0][0].body).toEqual({ name: 'Cases 2' });
    });

    it.each(ERROR_CODES)('shows a sentence for the refusal "%s"', async (code) => {
        queryState.data = [];
        createMock.mockResolvedValue({ error: { status: 422, data: { code, message: 'RAW SERVER TEXT' } } });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.ADD }));
        fillNew();
        fireEvent.click(screen.getByRole('button', { name: en.DIALOG.SAVE }));
        await waitFor(() => expect(createMock).toHaveBeenCalled());
        const dialog = await screen.findByRole('dialog');
        await waitFor(() => expect(dialog).toHaveTextContent(en.ERROR[code]));
        // our sentence, never the server's
        expect(dialog).not.toHaveTextContent('RAW SERVER TEXT');
        // tied to its field when it is about one, else announced
        const field = serviceErrorField(code);
        if (field) expect(dialog.querySelector('[aria-invalid="true"]')).not.toBeNull();
        else expect(within(dialog).getByRole('alert')).toHaveTextContent(en.ERROR[code]);
    });

    it('says the same in Dutch', async () => {
        await i18n.changeLanguage('nl');
        queryState.data = [];
        createMock.mockResolvedValue({ error: { status: 422, data: { code: 'invalid_url' } } });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: nl.SERVICES.ADD }));
        fireEvent.change(screen.getByLabelText(nl.DIALOG.NAME), { target: { value: 'Zaken' } });
        fireEvent.change(screen.getByLabelText(nl.DIALOG.ADDRESS), { target: { value: 'http://zaken.example.org' } });
        fireEvent.click(screen.getByRole('button', { name: nl.DIALOG.SAVE }));
        expect(await screen.findByText(nl.ERROR.invalid_url)).toBeInTheDocument();
    });
});

describe('Send test and delete', () => {
    it('shows our outcome code as a sentence', async () => {
        testMock.mockResolvedValue({ data: { ok: false, code: 'http_4xx', httpStatus: 403 } });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.TEST_NAMED.replace('{{name}}', 'Cases') }));
        await waitFor(() => expect(screen.getByTestId('registration-test-s1')).toHaveTextContent('The case system refused the test (HTTP 403). Check the address and the sign-in.'));
        expect(testMock).toHaveBeenCalledWith({ workspaceId: 'ws1', serviceId: 's1' });
        expect(screen.getByTestId('registration-test-s1')).toHaveAttribute('role', 'status');
    });

    it.each(TEST_CODES)('has a sentence for the test outcome "%s"', async (code) => {
        testMock.mockResolvedValue({ data: { ok: false, code, httpStatus: 500 } });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.TEST_NAMED.replace('{{name}}', 'Cases') }));
        const expected = (en.TEST[code] as string).replace('{{status}}', '500');
        await waitFor(() => expect(screen.getByTestId('registration-test-s1')).toHaveTextContent(expected));
    });

    it('says when the test arrived, and when the call itself failed', async () => {
        testMock.mockResolvedValueOnce({ data: { ok: true, httpStatus: 201 } }).mockResolvedValueOnce({ error: { status: 500 } });
        renderSection();
        const button = screen.getByRole('button', { name: en.SERVICES.TEST_NAMED.replace('{{name}}', 'Cases') });
        fireEvent.click(button);
        await waitFor(() => expect(screen.getByTestId('registration-test-s1')).toHaveTextContent(en.TEST.ok));
        fireEvent.click(button);
        await waitFor(() => expect(screen.getByTestId('registration-test-s1')).toHaveTextContent(en.TEST.unknown));
    });

    it('asks before deleting, and explains a service that is still in use', async () => {
        deleteMock.mockResolvedValueOnce({ error: { status: 409, data: { code: 'service_in_use' } } }).mockResolvedValueOnce({ data: undefined });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.DELETE_NAMED.replace('{{name}}', 'Cases') }));
        const dialog = await screen.findByRole('dialog');
        expect(deleteMock).not.toHaveBeenCalled();
        fireEvent.click(within(dialog).getByRole('button', { name: en.SERVICES.DELETE }));
        await waitFor(() => expect(within(dialog).getByRole('alert')).toHaveTextContent(en.ERROR.service_in_use));
        fireEvent.click(within(dialog).getByRole('button', { name: en.SERVICES.DELETE }));
        await waitFor(() => expect(toastMock).toHaveBeenCalledWith({ description: 'Cases was deleted.' }));
        expect(deleteMock).toHaveBeenLastCalledWith({ workspaceId: 'ws1', serviceId: 's1' });
    });
});

describe('Accessibility', () => {
    it('the list and the add dialog pass axe (WCAG 2.1 A/AA)', async () => {
        renderSection();
        expect(await axeViolations(document.body)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.ADD }));
        const dialog = await screen.findByRole('dialog');
        fireEvent.change(screen.getByLabelText(en.DIALOG.AUTH), { target: { value: 'basic' } });
        expect(await axeViolations(document.body)).toEqual([]);
        // the dialog is named, and keyboard focus is inside it
        expect(dialog).toHaveAccessibleName(en.DIALOG.ADD_TITLE);
        expect(dialog.contains(document.activeElement)).toBe(true);
    });

    it('shows the errors tied to their fields and passes axe', async () => {
        queryState.data = [];
        createMock.mockResolvedValue({ error: { status: 422, data: { code: 'invalid_url' } } });
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: en.SERVICES.ADD }));
        fillNew();
        fireEvent.click(screen.getByRole('button', { name: en.DIALOG.SAVE }));
        const address = await screen.findByLabelText(en.DIALOG.ADDRESS);
        await waitFor(() => expect(address).toHaveAccessibleDescription(expect.stringContaining(en.ERROR.invalid_url)));
        expect(await axeViolations(document.body)).toEqual([]);
    });
});
