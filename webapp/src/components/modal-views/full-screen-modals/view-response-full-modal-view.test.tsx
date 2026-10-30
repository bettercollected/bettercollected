import React, { useEffect } from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useGetWorkspacePermissionsQuery: () => ({ data: { permissions: [] }, isLoading: false, isError: false }) };
});

import FullScreenModalContainer from '@app/components/modal-views/full-screen-modal-container';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { FieldTypes } from '@app/models/dtos/form';
import I18nProvider from '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import ViewResponseFullModalView from './view-response-full-modal-view';

const choices = [
    { id: 'c1', value: 'Reading' },
    { id: 'c2', value: 'Cycling' },
    { id: 'c3', value: 'Cooking' }
];
const formFields: any[] = [
    { id: 'q1', type: FieldTypes.SHORT_TEXT, title: 'Full name' },
    { id: 'q2', type: FieldTypes.MULTIPLE_CHOICE, title: 'Hobbies', properties: { allowMultipleSelection: true, choices } }
];
const form: any = { formId: 'form-1', title: 'Survey', builderVersion: 'v1', settings: { provider: 'google' }, fields: formFields };

const known = {
    responseId: 'r1',
    provider: 'self',
    createdAt: '2026-10-30T09:10:05Z',
    updatedAt: '2026-10-30T09:10:05Z',
    dataOwnerIdentifier: 'known1@example.com',
    submissionUuid: '00123456',
    answers: {
        q1: { field: { id: 'q1' }, type: FieldTypes.SHORT_TEXT, text: 'Anna Example' },
        q2: { field: { id: 'q2' }, type: FieldTypes.MULTIPLE_CHOICE, choices: { values: ['c1', 'c2', 'c3'] } }
    }
};

const renderDrawer = (response: any) =>
    render(
        <ReduxProvider store={store}>
            <I18nProvider>
                <ViewResponseFullModalView response={response} formFields={formFields} form={form} formId="form-1" workspaceId="workspace-1" internalFields={[]} />
            </I18nProvider>
        </ReduxProvider>
    );

describe('response drawer', () => {
    beforeEach(() => {
        store.dispatch(setWorkspace({ id: 'workspace-1' } as any));
    });

    it('says who answered, when (with the time zone) and the submission number', () => {
        renderDrawer(known);
        expect(screen.getByRole('heading', { name: 'known1@example.com response' })).toBeInTheDocument();
        expect(screen.getByText(/^30 October 2026(,| at) \d{2}:\d{2}:\d{2} \S+$/)).toBeInTheDocument();
        expect(screen.getByText('#00123456')).toBeInTheDocument();
    });

    it('copies the submission number', async () => {
        const writeText = vi.fn(() => Promise.resolve());
        Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
        renderDrawer(known);
        fireEvent.click(screen.getByRole('button', { name: 'Copy submission number' }));
        await waitFor(() => expect(writeText).toHaveBeenCalledWith('00123456'));
        expect(await screen.findByText('Submission number copied')).toBeInTheDocument();
    });

    it('shows the Anonymous mark and no email for an anonymous response', () => {
        renderDrawer({ ...known, dataOwnerIdentifier: null, anonymousIdentity: 'anon' });
        expect(screen.getByRole('heading', { name: 'Anonymous response' })).toBeInTheDocument();
        expect(screen.queryByText('known1@example.com')).toBeNull();
    });

    it('hides the number and its copy button when the response has none', () => {
        renderDrawer({ ...known, submissionUuid: undefined });
        expect(screen.queryByRole('button', { name: 'Copy submission number' })).toBeNull();
    });

    it('joins a multi-select with a comma and a space', () => {
        renderDrawer(known);
        expect(screen.getByText('Reading, Cycling, Cooking')).toBeInTheDocument();
    });

    it('says the response could not be decrypted instead of "No answer"', () => {
        renderDrawer({ ...known, answers: {}, unreadableFields: ['answers'] });
        expect(screen.getAllByText('This response could not be decrypted').length).toBeGreaterThanOrEqual(3);
        expect(screen.queryByText('No answer')).toBeNull();
    });

    it('still says "No answer" for a readable response that has no answer', () => {
        renderDrawer({ ...known, answers: {} });
        expect(screen.getAllByText('No answer')).toHaveLength(2);
        expect(screen.queryByText(/could not be decrypted/)).toBeNull();
    });

    it('names what could not be read when only hidden or staff data failed', () => {
        renderDrawer({ ...known, unreadableFields: ['hidden_fields'] });
        expect(screen.getByText('Some data in this response could not be decrypted')).toBeInTheDocument();
        expect(screen.getByText(/hidden fields/)).toBeInTheDocument();
        expect(screen.getByText('Anna Example')).toBeInTheDocument();
    });
});

describe('response drawer dialog', () => {
    const Opener = () => {
        const { openModal } = useFullScreenModal();
        useEffect(() => {
            openModal('VIEW_RESPONSE', { response: known, formFields, form, formId: 'form-1', workspaceId: 'workspace-1', internalFields: [] });
        }, []);
        return null;
    };

    it('is a dialog named after the responder', async () => {
        render(
            <ReduxProvider store={store}>
                <I18nProvider>
                    <Opener />
                    <FullScreenModalContainer />
                </I18nProvider>
            </ReduxProvider>
        );
        expect(await screen.findByRole('dialog', { name: 'known1@example.com response' })).toBeInTheDocument();
    });
});
