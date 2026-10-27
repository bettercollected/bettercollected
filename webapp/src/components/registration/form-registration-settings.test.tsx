import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import type { FormRegistration, RegistrationService, RegistrationVariable } from '@app/store/workspaces/registration-api';
import { axeViolations } from '@app/test/axe';
import { ERROR_CODES, formErrorField } from '@app/utils/registration';

import enBuilder from '../../../public/locales/en/builder.json';
import nlBuilder from '../../../public/locales/nl/builder.json';
import FormRegistrationSection, { FormRegistrationSettings } from './form-registration-settings';

// Radix's switch measures itself with a ResizeObserver, which jsdom lacks.
vi.stubGlobal(
    'ResizeObserver',
    class {
        observe() {}
        unobserve() {}
        disconnect() {}
    }
);

const en = enBuilder.REGISTRATION as any;
const nl = nlBuilder.REGISTRATION as any;

const status = { data: { enabled: true } as { enabled: boolean } | undefined, isLoading: false };
const registrationState: { data: FormRegistration | undefined; isLoading: boolean; isError: boolean } = { data: undefined, isLoading: false, isError: false };
const servicesState: { data: RegistrationService[] | undefined; isLoading: boolean } = { data: [], isLoading: false };
const variablesState: { data: RegistrationVariable[] | undefined; isLoading: boolean; isError: boolean } = { data: [], isLoading: false, isError: false };
const saveMock = vi.fn();
vi.mock('@app/store/workspaces/registration-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetRegistrationStatusQuery: () => status,
        useGetFormRegistrationQuery: () => registrationState,
        useGetRegistrationServicesQuery: () => servicesState,
        useGetRegistrationVariablesQuery: () => variablesState,
        useSaveFormRegistrationMutation: () => [saveMock, { isLoading: false }]
    };
});

let permissions = new Set<string>([WorkspacePermission.WORKSPACE_MANAGE]);
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: (p: string) => permissions.has(p), ready: true, isLoading: false }) }));
let formState: any = { formId: 'f1', settings: { provider: 'self' } };
vi.mock('@app/store/forms/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectForm: () => formState };
});
vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', workspaceName: 'acme', title: 'Acme' }) };
});

const wrapper = ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider>;

const services: RegistrationService[] = [
    { id: 's1', name: 'Cases', kind: 'generic_json', baseUrl: 'https://cases.example.org', auth: 'none', hasSecret: false, organisationName: 'Example Organisation' },
    { id: 's2', name: 'Archive', kind: 'generic_json', baseUrl: 'https://archive.example.org', auth: 'none', hasSecret: false, organisationName: 'Example Organisation' }
];
const variables: RegistrationVariable[] = [
    { source: 'q1', label: 'Postcode', type: 'short_text', supported: true },
    { source: 'q2', label: 'Interests', type: 'multiple_choice', supported: true },
    { source: 'q3', label: 'Photo of the damage', type: 'file_upload', supported: true },
    { source: 'q4', label: 'Welcome text', type: 'statement', supported: false, reason: 'not_an_answer' },
    { source: 'q5', label: 'Signature', type: 'signature', supported: false, reason: 'type_not_supported' },
    { source: 'ref', label: 'ref', type: 'hidden', supported: true }
];
const registration = (over: Partial<FormRegistration> = {}): FormRegistration => ({ enabled: false, serviceId: null, serviceName: null, organisationName: null, path: '', variables: [], transformToList: [], ...over });

beforeEach(() => {
    status.data = { enabled: true };
    registrationState.data = registration();
    registrationState.isError = false;
    servicesState.data = services;
    variablesState.data = variables;
    variablesState.isError = false;
    permissions = new Set([WorkspacePermission.WORKSPACE_MANAGE]);
    formState = { formId: 'f1', settings: { provider: 'self' } };
    saveMock.mockReset();
});
afterEach(async () => {
    await i18n.changeLanguage('en');
});

const renderSettings = () => render(<FormRegistrationSettings workspaceId="ws1" workspaceName="acme" formId="f1" />, { wrapper });
const toggle = () => screen.getByRole('switch', { name: en.FORM.ENABLE });

describe('Visibility of the section', () => {
    it('is hidden when the server has the feature off', () => {
        status.data = { enabled: false };
        const { container } = render(<FormRegistrationSection />, { wrapper });
        expect(container).toBeEmptyDOMElement();
    });

    it('is hidden while the status has not arrived, for anyone but owners and admins, and for imported forms', () => {
        status.data = undefined;
        expect(render(<FormRegistrationSection />, { wrapper }).container).toBeEmptyDOMElement();
        status.data = { enabled: true };
        permissions = new Set([WorkspacePermission.FORM_EDIT, WorkspacePermission.FORM_READ]);
        expect(render(<FormRegistrationSection />, { wrapper }).container).toBeEmptyDOMElement();
        permissions = new Set([WorkspacePermission.WORKSPACE_MANAGE]);
        formState = { formId: 'f1', settings: { provider: 'google' } };
        expect(render(<FormRegistrationSection />, { wrapper }).container).toBeEmptyDOMElement();
    });

    it('shows for an admin on a form made here', () => {
        render(<FormRegistrationSection />, { wrapper });
        expect(screen.getByRole('heading', { name: en.FORM.TITLE })).toBeInTheDocument();
    });
});

describe('Settings', () => {
    it('explains that only the chosen answers leave and that earlier submissions are not sent', () => {
        renderSettings();
        expect(screen.getByText(en.FORM.INTRO)).toBeInTheDocument();
        expect(screen.getByText(en.FORM.LATER_ONLY)).toBeInTheDocument();
        expect(screen.getByText(en.NOTICE)).toBeInTheDocument();
        expect(toggle()).toHaveAttribute('aria-checked', 'false');
        // nothing to choose while it is off
        expect(screen.queryByLabelText(en.FORM.SERVICE)).toBeNull();
    });

    it('greys out what cannot be sent, with the reason', () => {
        renderSettings();
        fireEvent.click(toggle());
        const note = screen.getByTestId('registration-variable-q4');
        expect(within(note).getByRole('checkbox')).toBeDisabled();
        expect(note).toHaveTextContent(en.FORM.REASON.not_an_answer);
        expect(within(screen.getByTestId('registration-variable-q5')).getByRole('checkbox')).toBeDisabled();
        expect(screen.getByTestId('registration-variable-q5')).toHaveTextContent(en.FORM.REASON.type_not_supported);
        expect(within(screen.getByTestId('registration-variable-q1')).getByRole('checkbox')).toBeEnabled();
    });

    it('saves the service, the path, the chosen variables with their names and the list option', async () => {
        saveMock.mockResolvedValue({ data: registration({ enabled: true }) });
        renderSettings();
        fireEvent.click(toggle());
        fireEvent.change(screen.getByLabelText(en.FORM.SERVICE), { target: { value: 's2' } });
        fireEvent.change(screen.getByLabelText(en.FORM.PATH), { target: { value: '/cases' } });
        fireEvent.click(within(screen.getByTestId('registration-variable-q1')).getByRole('checkbox'));
        fireEvent.change(within(screen.getByTestId('registration-variable-q1')).getByLabelText(en.FORM.KEY), { target: { value: 'postcode' } });
        fireEvent.click(within(screen.getByTestId('registration-variable-q2')).getByRole('checkbox'));
        // "send as list" only for multiple choice
        expect(within(screen.getByTestId('registration-variable-q1')).queryByLabelText(en.FORM.AS_LIST)).toBeNull();
        fireEvent.click(within(screen.getByTestId('registration-variable-q2')).getByLabelText(en.FORM.AS_LIST));
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        await waitFor(() => expect(saveMock).toHaveBeenCalledTimes(1));
        expect(saveMock).toHaveBeenCalledWith({
            workspaceId: 'ws1',
            formId: 'f1',
            body: {
                enabled: true,
                serviceId: 's2',
                path: '/cases',
                variables: [
                    { source: 'q1', key: 'postcode' },
                    { source: 'q2', key: undefined }
                ],
                transformToList: ['q2']
            }
        });
        expect(await screen.findByText(en.FORM.SAVED)).toBeInTheDocument();
    });

    it('loads what was saved, and leaves out chosen answers that are no longer in the form', () => {
        registrationState.data = registration({
            enabled: true,
            serviceId: 's2',
            path: '/zaken',
            variables: [
                { source: 'q2', key: 'interests' },
                { source: 'gone', key: 'old' }
            ],
            transformToList: ['q2']
        });
        renderSettings();
        expect(toggle()).toHaveAttribute('aria-checked', 'true');
        expect(screen.getByLabelText(en.FORM.SERVICE)).toHaveValue('s2');
        expect(screen.getByLabelText(en.FORM.PATH)).toHaveValue('/zaken');
        const row = screen.getByTestId('registration-variable-q2');
        expect(within(row).getByRole('checkbox', { name: 'Interests' })).toBeChecked();
        expect(within(row).getByLabelText(en.FORM.KEY)).toHaveValue('interests');
        expect(within(row).getByLabelText(en.FORM.AS_LIST)).toBeChecked();
        expect(screen.getByText(/1 chosen answer is no longer in this form/)).toBeInTheDocument();
    });

    it('does not save without a service or an answer, and names a duplicate or invalid key', async () => {
        renderSettings();
        fireEvent.click(toggle());
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(saveMock).not.toHaveBeenCalled();
        expect(screen.getByLabelText(en.FORM.SERVICE)).toHaveAccessibleDescription(en.ERROR.service_required);
        expect(screen.getByText(en.ERROR.variables_required)).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText(en.FORM.SERVICE), { target: { value: 's1' } });
        fireEvent.click(within(screen.getByTestId('registration-variable-q1')).getByRole('checkbox'));
        fireEvent.click(within(screen.getByTestId('registration-variable-q2')).getByRole('checkbox'));
        fireEvent.change(within(screen.getByTestId('registration-variable-q1')).getByLabelText(en.FORM.KEY), { target: { value: 'same' } });
        fireEvent.change(within(screen.getByTestId('registration-variable-q2')).getByLabelText(en.FORM.KEY), { target: { value: 'same' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(saveMock).not.toHaveBeenCalled();
        const second = within(screen.getByTestId('registration-variable-q2')).getByLabelText(en.FORM.KEY);
        expect(second).toHaveAttribute('aria-invalid', 'true');
        expect(second).toHaveAccessibleDescription(en.FORM.KEY_TAKEN);

        fireEvent.change(second, { target: { value: '1bad' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(second).toHaveAccessibleDescription(en.ERROR.invalid_key);
        expect(saveMock).not.toHaveBeenCalled();
    });

    it('can turn sending off without choosing anything', async () => {
        registrationState.data = registration({ enabled: true, serviceId: 's1', variables: [{ source: 'q1', key: 'postcode' }] });
        saveMock.mockResolvedValue({ data: registration() });
        renderSettings();
        fireEvent.click(toggle());
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        await waitFor(() => expect(saveMock).toHaveBeenCalled());
        expect(saveMock.mock.calls[0][0].body).toMatchObject({ enabled: false });
    });

    it.each(ERROR_CODES)('shows a sentence for the refusal "%s"', async (code) => {
        saveMock.mockResolvedValue({ error: { status: 422, data: { code, message: 'RAW SERVER TEXT' } } });
        registrationState.data = registration({ enabled: true, serviceId: 's1', variables: [{ source: 'q1', key: 'postcode' }] });
        renderSettings();
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        await waitFor(() => expect(saveMock).toHaveBeenCalled());
        await waitFor(() => expect(document.body).toHaveTextContent(en.ERROR[code]));
        expect(document.body).not.toHaveTextContent('RAW SERVER TEXT');
        if (!formErrorField(code)) expect(screen.getByRole('alert')).toHaveTextContent(en.ERROR[code]);
    });

    it('points to the workspace settings when there is no case system yet', () => {
        servicesState.data = [];
        renderSettings();
        fireEvent.click(toggle());
        expect(screen.getByRole('link', { name: en.FORM.ADD_SERVICE })).toHaveAttribute('href', '/acme/dashboard/case-system');
    });

    it('speaks Dutch', async () => {
        await i18n.changeLanguage('nl');
        renderSettings();
        expect(screen.getByRole('heading', { name: nl.FORM.TITLE })).toBeInTheDocument();
        expect(screen.getByText(nl.FORM.LATER_ONLY)).toBeInTheDocument();
    });
});

describe('Accessibility', () => {
    it('passes axe (WCAG 2.1 A/AA) with sending on, a chosen answer and an error', async () => {
        registrationState.data = registration({ enabled: true, serviceId: 's1', variables: [{ source: 'q2', key: 'interests' }] });
        renderSettings();
        fireEvent.change(within(screen.getByTestId('registration-variable-q2')).getByLabelText(en.FORM.KEY), { target: { value: '1bad' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(await screen.findByText(en.ERROR.invalid_key)).toBeInTheDocument();
        expect(await axeViolations(document.body)).toEqual([]);
    });
});
