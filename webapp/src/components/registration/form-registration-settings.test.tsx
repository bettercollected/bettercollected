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
const checkMock = vi.fn();
vi.mock('@app/store/workspaces/registration-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetRegistrationStatusQuery: () => status,
        useGetFormRegistrationQuery: () => registrationState,
        useGetRegistrationServicesQuery: () => servicesState,
        useGetRegistrationVariablesQuery: () => variablesState,
        useSaveFormRegistrationMutation: () => [saveMock, { isLoading: false }],
        useCheckFormRegistrationMutation: () => [checkMock, { isLoading: false }]
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
    checkMock.mockReset();
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

const OT_ID = '0f9a3b1c-5d2e-4f6a-8b7c-1d2e3f4a5b6c';
const OT_URL = `https://types.example.org/api/v2/objecttypes/${OT_ID}`;
const objectsServices: RegistrationService[] = [
    ...services,
    {
        id: 's9',
        name: 'Objects',
        kind: 'objects_api',
        baseUrl: 'https://objects.example.org/api/v2/',
        objecttypesBaseUrl: 'https://types.example.org/api/v2/',
        auth: 'token',
        hasSecret: true,
        organisationName: 'Example Organisation'
    }
];
const objectsRegistration = (over: Partial<FormRegistration> = {}) =>
    registration({
        enabled: true,
        serviceId: 's9',
        serviceName: 'Objects',
        kind: 'objects_api',
        objectTypeUrl: OT_URL,
        objectTypeVersion: 3,
        referencePath: ['bettercollected_reference'],
        variables: [{ source: 'q1', key: null, targetPath: ['applicant', 'postcode'] }],
        ...over
    });
const within_ = (id: string) => within(screen.getByTestId(`registration-variable-${id}`));

describe('Objects API form settings', () => {
    beforeEach(() => {
        servicesState.data = objectsServices;
    });

    it('shows the object type fields instead of the path once an Objects API service is chosen', () => {
        renderSettings();
        fireEvent.click(toggle());
        expect(screen.getByLabelText(en.FORM.PATH)).toBeInTheDocument();
        expect(screen.queryByLabelText(en.FORM.OBJECT_TYPE_URL)).toBeNull();
        fireEvent.change(screen.getByLabelText(en.FORM.SERVICE), { target: { value: 's9' } });
        expect(screen.queryByLabelText(en.FORM.PATH)).toBeNull();
        expect(screen.getByLabelText(en.FORM.OBJECT_TYPE_URL)).toHaveAccessibleDescription(expect.stringContaining('https://types.example.org/api/v2/'));
        expect(screen.getByLabelText(en.FORM.OBJECT_TYPE_VERSION)).toBeInTheDocument();
        // the default reference path is filled in
        expect(screen.getByLabelText(en.FORM.REFERENCE_PATH)).toHaveValue('bettercollected_reference');
        expect(screen.getByText(en.FORM.OBJECTS_HELP)).toBeInTheDocument();
        expect(screen.getByText(en.FORM.OBJECTS_EDGE)).toBeInTheDocument();
        expect(screen.getByText(en.NOTICE)).toBeInTheDocument();
    });

    it('shows target paths instead of names, has no list option, and shows files as not supported', () => {
        registrationState.data = objectsRegistration();
        renderSettings();
        const row = within_('q1');
        expect(row.getByLabelText(en.FORM.TARGET_PATH)).toHaveValue('applicant.postcode');
        expect(row.queryByLabelText(en.FORM.KEY)).toBeNull();
        fireEvent.click(within_('q2').getByRole('checkbox'));
        expect(within_('q2').queryByLabelText(en.FORM.AS_LIST)).toBeNull();
        const file = screen.getByTestId('registration-variable-q3');
        expect(within(file).getByRole('checkbox')).toBeDisabled();
        expect(within(file).getByRole('checkbox')).not.toBeChecked();
        expect(file).toHaveTextContent(en.FORM.REASON.file_upload);
        // the generic "always sent" line does not apply: only the mapped answers and the reference go out
        expect(screen.queryByText(en.FORM.ALWAYS_SENT)).toBeNull();
    });

    it('saves the object type, version, reference path and the target paths as segments', async () => {
        saveMock.mockResolvedValue({ data: objectsRegistration() });
        renderSettings();
        fireEvent.click(toggle());
        fireEvent.change(screen.getByLabelText(en.FORM.SERVICE), { target: { value: 's9' } });
        fireEvent.change(screen.getByLabelText(en.FORM.OBJECT_TYPE_URL), { target: { value: ` ${OT_URL} ` } });
        fireEvent.change(screen.getByLabelText(en.FORM.OBJECT_TYPE_VERSION), { target: { value: '3' } });
        fireEvent.click(within_('q1').getByRole('checkbox'));
        fireEvent.change(within_('q1').getByLabelText(en.FORM.TARGET_PATH), { target: { value: 'applicant.postcode' } });
        fireEvent.click(within_('q2').getByRole('checkbox'));
        fireEvent.change(within_('q2').getByLabelText(en.FORM.TARGET_PATH), { target: { value: 'interests' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        await waitFor(() => expect(saveMock).toHaveBeenCalledTimes(1));
        expect(saveMock).toHaveBeenCalledWith({
            workspaceId: 'ws1',
            formId: 'f1',
            body: {
                enabled: true,
                serviceId: 's9',
                path: '',
                variables: [
                    { source: 'q1', targetPath: ['applicant', 'postcode'] },
                    { source: 'q2', targetPath: ['interests'] }
                ],
                transformToList: [],
                objectTypeUrl: OT_URL,
                objectTypeVersion: 3,
                referencePath: ['bettercollected_reference']
            }
        });
    });

    it('never sends a mapped file question, even one left over from another service', async () => {
        saveMock.mockResolvedValue({ data: objectsRegistration() });
        registrationState.data = registration({
            enabled: true,
            serviceId: 's1',
            variables: [
                { source: 'q3', key: 'photo' },
                { source: 'q1', key: 'postcode' }
            ]
        });
        renderSettings();
        fireEvent.change(screen.getByLabelText(en.FORM.SERVICE), { target: { value: 's9' } });
        fireEvent.change(screen.getByLabelText(en.FORM.OBJECT_TYPE_URL), { target: { value: OT_URL } });
        fireEvent.change(screen.getByLabelText(en.FORM.OBJECT_TYPE_VERSION), { target: { value: '1' } });
        fireEvent.change(within_('q1').getByLabelText(en.FORM.TARGET_PATH), { target: { value: 'pc' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        await waitFor(() => expect(saveMock).toHaveBeenCalled());
        expect(saveMock.mock.calls[0][0].body.variables).toEqual([{ source: 'q1', targetPath: ['pc'] }]);
    });

    it('checks the object type address against the service base before sending', () => {
        registrationState.data = objectsRegistration();
        renderSettings();
        const field = screen.getByLabelText(en.FORM.OBJECT_TYPE_URL);
        fireEvent.change(field, { target: { value: `https://evil.example.org/api/v2/objecttypes/${OT_ID}` } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(saveMock).not.toHaveBeenCalled();
        expect(field).toHaveAttribute('aria-invalid', 'true');
        expect(field).toHaveAccessibleDescription(expect.stringContaining(en.ERROR.object_type_outside_base));
        fireEvent.change(field, { target: { value: 'not a url' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(field).toHaveAccessibleDescription(expect.stringContaining(en.ERROR.invalid_object_type_url));
        expect(saveMock).not.toHaveBeenCalled();
    });

    it('refuses a bad version, bad or clashing target paths and a clashing reference path', () => {
        registrationState.data = objectsRegistration({
            variables: [
                { source: 'q1', targetPath: ['a'] },
                { source: 'q2', targetPath: ['b'] }
            ]
        });
        renderSettings();
        fireEvent.change(screen.getByLabelText(en.FORM.OBJECT_TYPE_VERSION), { target: { value: '0' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(screen.getByLabelText(en.FORM.OBJECT_TYPE_VERSION)).toHaveAccessibleDescription(expect.stringContaining(en.ERROR.invalid_object_type_version));
        fireEvent.change(screen.getByLabelText(en.FORM.OBJECT_TYPE_VERSION), { target: { value: '2' } });

        fireEvent.change(within_('q1').getByLabelText(en.FORM.TARGET_PATH), { target: { value: 'a__b' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(within_('q1').getByLabelText(en.FORM.TARGET_PATH)).toHaveAccessibleDescription(en.ERROR.invalid_target_path);

        fireEvent.change(within_('q1').getByLabelText(en.FORM.TARGET_PATH), { target: { value: 'a' } });
        fireEvent.change(within_('q2').getByLabelText(en.FORM.TARGET_PATH), { target: { value: 'a.b' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(within_('q2').getByLabelText(en.FORM.TARGET_PATH)).toHaveAccessibleDescription(en.FORM.TARGET_TAKEN);

        fireEvent.change(within_('q2').getByLabelText(en.FORM.TARGET_PATH), { target: { value: 'b' } });
        fireEvent.change(screen.getByLabelText(en.FORM.REFERENCE_PATH), { target: { value: 'a.ref' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(screen.getByLabelText(en.FORM.REFERENCE_PATH)).toHaveAccessibleDescription(expect.stringContaining(en.ERROR.reference_path_conflict));

        fireEvent.change(screen.getByLabelText(en.FORM.REFERENCE_PATH), { target: { value: 'bad-name' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(screen.getByLabelText(en.FORM.REFERENCE_PATH)).toHaveAccessibleDescription(expect.stringContaining(en.ERROR.invalid_reference_path));
        expect(saveMock).not.toHaveBeenCalled();
    });

    it('uses the default reference path when the field is emptied', async () => {
        saveMock.mockResolvedValue({ data: objectsRegistration() });
        registrationState.data = objectsRegistration();
        renderSettings();
        fireEvent.change(screen.getByLabelText(en.FORM.REFERENCE_PATH), { target: { value: '' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        await waitFor(() => expect(saveMock).toHaveBeenCalled());
        expect(saveMock.mock.calls[0][0].body.referencePath).toEqual(['bettercollected_reference']);
    });

    it('shows a server refusal of the object type next to the field', async () => {
        saveMock.mockResolvedValue({ error: { status: 422, data: { code: 'object_type_outside_base', message: 'RAW SERVER TEXT' } } });
        registrationState.data = objectsRegistration();
        renderSettings();
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        await waitFor(() => expect(screen.getByLabelText(en.FORM.OBJECT_TYPE_URL)).toHaveAccessibleDescription(expect.stringContaining(en.ERROR.object_type_outside_base)));
        expect(document.body).not.toHaveTextContent('RAW SERVER TEXT');
    });
});

describe('Turning an Objects API form off', () => {
    beforeEach(() => {
        servicesState.data = objectsServices;
    });

    it('works with an object type address that is outside the service base now', async () => {
        saveMock.mockResolvedValue({ data: objectsRegistration({ enabled: false }) });
        registrationState.data = objectsRegistration({ objectTypeUrl: `https://old.example.org/api/v2/objecttypes/${OT_ID}` });
        renderSettings();
        fireEvent.click(toggle());
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        await waitFor(() => expect(saveMock).toHaveBeenCalledTimes(1));
        expect(saveMock.mock.calls[0][0].body).toEqual({ enabled: false, serviceId: 's9', path: '', variables: [], transformToList: [] });
        expect(await screen.findByText(en.FORM.SAVED)).toBeInTheDocument();
    });

    it('works with empty or invalid target paths, and says nothing is wrong', async () => {
        saveMock.mockResolvedValue({ data: objectsRegistration({ enabled: false }) });
        registrationState.data = objectsRegistration({ variables: [{ source: 'q1', targetPath: [] }] });
        renderSettings();
        fireEvent.change(within_('q1').getByLabelText(en.FORM.TARGET_PATH), { target: { value: '' } });
        fireEvent.click(toggle());
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        await waitFor(() => expect(saveMock).toHaveBeenCalledTimes(1));
        expect(saveMock.mock.calls[0][0].body.enabled).toBe(false);
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it("shows the server's refusal of the off save", async () => {
        saveMock.mockResolvedValue({ error: { status: 404, data: { code: 'service_not_found' } } });
        registrationState.data = objectsRegistration();
        renderSettings();
        fireEvent.click(toggle());
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(await screen.findByRole('alert')).toHaveTextContent(en.ERROR.service_not_found);
    });

    it('never stops silently when switched on: marks the fields and says nothing was saved', () => {
        registrationState.data = objectsRegistration({ variables: [{ source: 'q1', targetPath: ['a'] }] });
        renderSettings();
        fireEvent.change(within_('q1').getByLabelText(en.FORM.TARGET_PATH), { target: { value: 'bad path' } });
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        expect(saveMock).not.toHaveBeenCalled();
        expect(screen.getByRole('alert')).toHaveTextContent(en.FORM.FIX_ERRORS);
        expect(within_('q1').getByLabelText(en.FORM.TARGET_PATH)).toHaveAttribute('aria-invalid', 'true');
    });

    it('checks the connection from what the save answered, before the settings are read again', async () => {
        // the query still holds a form without a service
        registrationState.data = registration();
        saveMock.mockResolvedValue({ data: objectsRegistration() });
        renderSettings();
        fireEvent.click(toggle());
        fireEvent.change(screen.getByLabelText(en.FORM.SERVICE), { target: { value: 's9' } });
        fireEvent.change(screen.getByLabelText(en.FORM.OBJECT_TYPE_URL), { target: { value: OT_URL } });
        fireEvent.change(screen.getByLabelText(en.FORM.OBJECT_TYPE_VERSION), { target: { value: '3' } });
        fireEvent.click(within_('q1').getByRole('checkbox'));
        fireEvent.change(within_('q1').getByLabelText(en.FORM.TARGET_PATH), { target: { value: 'applicant.postcode' } });
        expect(screen.getByRole('button', { name: en.FORM.CHECK })).toBeDisabled();
        fireEvent.click(screen.getByRole('button', { name: en.FORM.SAVE }));
        await screen.findByText(en.FORM.SAVED);
        expect(screen.getByRole('button', { name: en.FORM.CHECK })).toBeEnabled();
    });
});

describe('Check connection', () => {
    beforeEach(() => {
        servicesState.data = objectsServices;
        registrationState.data = objectsRegistration();
    });
    const button = () => screen.getByRole('button', { name: en.FORM.CHECK });
    const result = () => screen.getByTestId('registration-check-result');

    it('is shown only for an Objects API service', () => {
        registrationState.data = registration({ enabled: true, serviceId: 's1', kind: 'generic_json', variables: [{ source: 'q1', key: 'x' }] });
        renderSettings();
        expect(screen.queryByRole('button', { name: en.FORM.CHECK })).toBeNull();
    });

    it('is off until the changes are saved, then says it uses the saved settings', () => {
        renderSettings();
        expect(button()).toBeEnabled();
        expect(screen.getByText(en.FORM.CHECK_HINT)).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText(en.FORM.OBJECT_TYPE_VERSION), { target: { value: '4' } });
        expect(button()).toBeDisabled();
        expect(screen.getByText(en.FORM.CHECK_SAVE_FIRST)).toBeInTheDocument();
    });

    it('reports success', async () => {
        checkMock.mockResolvedValue({ data: { ok: true } });
        renderSettings();
        fireEvent.click(button());
        expect(checkMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1' });
        await waitFor(() => expect(result()).toHaveTextContent(en.CHECK.ok));
        expect(result()).not.toHaveClass('text-[#A83434]');
    });

    it.each([
        ['lookup_failed', undefined],
        ['filter_not_supported', undefined],
        ['not_configured', undefined],
        ['secret_unreadable', undefined],
        ['http_5xx', 502]
    ])('reports "%s" in plain words', async (code, httpStatus) => {
        checkMock.mockResolvedValue({ data: { ok: false, code, httpStatus } });
        renderSettings();
        fireEvent.click(button());
        await waitFor(() => expect(result()).toHaveTextContent((en.CHECK[code] as string).replace('{{status}}', String(httpStatus))));
        expect(result()).toHaveClass('text-[#A83434]');
    });

    it('says "too many checks" on a 429, and never shows the server text', async () => {
        checkMock.mockResolvedValue({ error: { status: 429, data: { code: 'rate_limited', message: 'RAW SERVER TEXT' } } });
        renderSettings();
        fireEvent.click(button());
        await waitFor(() => expect(result()).toHaveTextContent(en.CHECK.rate_limited));
        expect(document.body).not.toHaveTextContent('RAW SERVER TEXT');
        // and can be run again
        expect(button()).toBeEnabled();
    });

    it('answers a forbidden or failed call with a sentence too', async () => {
        checkMock.mockResolvedValue({ error: { status: 403 } });
        renderSettings();
        fireEvent.click(button());
        await waitFor(() => expect(result()).toHaveTextContent(en.ERROR.forbidden));
    });

    it('clears an old result when something is edited', async () => {
        checkMock.mockResolvedValue({ data: { ok: true } });
        renderSettings();
        fireEvent.click(button());
        await waitFor(() => expect(result()).toHaveTextContent(en.CHECK.ok));
        fireEvent.change(screen.getByLabelText(en.FORM.REFERENCE_PATH), { target: { value: 'x' } });
        expect(result()).toBeEmptyDOMElement();
    });

    it('speaks Dutch in the "u" register', async () => {
        await i18n.changeLanguage('nl');
        checkMock.mockResolvedValue({ data: { ok: false, code: 'lookup_failed' } });
        renderSettings();
        fireEvent.click(screen.getByRole('button', { name: nl.FORM.CHECK }));
        await waitFor(() => expect(result()).toHaveTextContent(nl.CHECK.lookup_failed));
        expect(screen.getByText(nl.FORM.OBJECTS_HELP)).toBeInTheDocument();
    });

    it('has no accessibility violations', async () => {
        const { container } = renderSettings();
        expect(await axeViolations(container)).toEqual([]);
    });
});
