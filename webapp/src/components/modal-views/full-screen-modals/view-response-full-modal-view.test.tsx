import React, { useEffect } from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
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
    submissionUuid: '0a1b2c3d-1111-4222-8333-444455556666',
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

    it('says who answered, when (with the time zone) and the start of the submission number', () => {
        renderDrawer(known);
        expect(screen.getByRole('heading', { name: 'known1@example.com response' })).toBeInTheDocument();
        expect(screen.getByText(/^30 October 2026(,| at) \d{2}:\d{2}:\d{2} \S+$/)).toBeInTheDocument();
        expect(screen.getByText('#0a1b2c3d…')).toBeInTheDocument();
    });

    it('never shows the full receipt number (it is a bearer token) and offers no copy button', () => {
        const { container } = renderDrawer(known);
        expect(container.textContent).not.toContain('4222');
        expect(container.textContent).not.toContain('444455556666');
        expect(container.querySelector('[title*="0a1b2c3d"]')).toBeNull();
        expect(screen.queryByRole('button', { name: /copy/i })).toBeNull();
    });

    it('shows the Anonymous mark and no email for an anonymous response', () => {
        renderDrawer({ ...known, dataOwnerIdentifier: null, anonymousIdentity: 'anon' });
        expect(screen.getByRole('heading', { name: 'Anonymous response' })).toBeInTheDocument();
        expect(screen.queryByText('known1@example.com')).toBeNull();
    });

    it('shows no number line when the response has none', () => {
        renderDrawer({ ...known, submissionUuid: undefined });
        expect(screen.queryByText(/^#/)).toBeNull();
    });

    it('joins the options of a multi-select answer with ", "', () => {
        renderDrawer(known);
        expect(screen.getByText('Reading, Cycling, Cooking')).toBeInTheDocument();
        expect(screen.queryByText('Reading,Cycling,Cooking')).toBeNull();
    });

    it('joins a multi-select answer inside a repeating group with ", " too (not the export\'s "; ")', () => {
        const group = { id: 'g', type: FieldTypes.GROUP, title: 'Kids', properties: { repeat: { minItems: 1, maxItems: 3, itemLabel: 'Kid' }, fields: [{ ...formFields[1], id: 'k1' }] } };
        const answers = { g: { items: [{ k1: { field: { id: 'k1' }, type: FieldTypes.MULTIPLE_CHOICE, choices: { values: ['c1', 'c3'] } } }] } };
        render(
            <ReduxProvider store={store}>
                <I18nProvider>
                    <ViewResponseFullModalView response={{ ...known, answers } as any} formFields={[group as any]} form={{ ...form, fields: [group] }} formId="form-1" workspaceId="workspace-1" internalFields={[]} />
                </I18nProvider>
            </ReduxProvider>
        );
        expect(screen.getByText('Reading, Cooking')).toBeInTheDocument();
        expect(screen.queryByText('Reading; Cooking')).toBeNull();
    });

    it('shortens a receipt number without dashes too', () => {
        const { container } = renderDrawer({ ...known, submissionUuid: '0a1b2c3d111142228333444455556666' });
        expect(screen.getByText('#0a1b2c3d…')).toBeInTheDocument();
        expect(container.textContent).not.toContain('0a1b2c3d1111');
    });

    it('says once that the response could not be decrypted, and keeps the per-question text short', () => {
        renderDrawer({ ...known, answers: {}, unreadableFields: ['answers'] });
        expect(screen.getAllByText('This response could not be decrypted')).toHaveLength(1);
        expect(screen.getAllByText('Could not be decrypted')).toHaveLength(2);
        expect(screen.queryByText('No answer')).toBeNull();
        // plain text: it is there on open, so a live region would announce nothing
        expect(screen.queryByRole('status')).toBeNull();
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it('still says "No answer" for a readable response that has no answer', () => {
        renderDrawer({ ...known, answers: {} });
        expect(screen.getAllByText('No answer')).toHaveLength(2);
        expect(screen.queryByText(/could not be decrypted/i)).toBeNull();
    });

    it('names what could not be read when only hidden or staff data failed', () => {
        renderDrawer({ ...known, unreadableFields: ['hidden_fields'] });
        expect(screen.getByText('Some data in this response could not be decrypted')).toBeInTheDocument();
        expect(screen.getByText(/hidden fields/)).toBeInTheDocument();
        expect(screen.getByText('Anna Example')).toBeInTheDocument();
        expect(screen.queryByText('Could not be decrypted')).toBeNull();
    });
});

describe('response drawer dialog', () => {
    const Opener = ({ response }: { response: any }) => {
        const { openModal, closeModal } = useFullScreenModal();
        useEffect(() => {
            openModal('VIEW_RESPONSE', { response, formFields, form, formId: 'form-1', workspaceId: 'workspace-1', internalFields: [] });
        }, []);
        return <button onClick={closeModal}>close from outside</button>;
    };
    const renderOpened = (response: any) =>
        render(
            <ReduxProvider store={store}>
                <I18nProvider>
                    <Opener response={response} />
                    <FullScreenModalContainer />
                </I18nProvider>
            </ReduxProvider>
        );

    it('is a dialog named after the responder', async () => {
        renderOpened(known);
        expect(await screen.findByRole('dialog', { name: 'known1@example.com response' })).toBeInTheDocument();
    });

    it('is named "Anonymous response" when there is no email', async () => {
        renderOpened({ ...known, dataOwnerIdentifier: null, anonymousIdentity: 'anon' });
        expect(await screen.findByRole('dialog', { name: 'Anonymous response' })).toBeInTheDocument();
    });

    it('keeps its name while it leaves the screen', async () => {
        renderOpened(known);
        const dialog = await screen.findByRole('dialog', { name: 'known1@example.com response' });
        act(() => {
            fireEvent.click(screen.getByText('close from outside'));
        });
        // closing clears the view at once; whatever is still on screen keeps its name
        screen.queryAllByRole('dialog', { hidden: true }).forEach((leaving) => expect(leaving).toHaveAttribute('aria-label', 'known1@example.com response'));
        expect(dialog.getAttribute('aria-label')).toBe('known1@example.com response');
    });
});
