import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import I18nProvider from '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import { IndividualFormResponse } from './individual-form-response';

// the respondent's own receipt page draws the response with this component
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
    answers: {
        q1: { field: { id: 'q1' }, type: FieldTypes.SHORT_TEXT, text: 'Anna Example' },
        q2: { field: { id: 'q2' }, type: FieldTypes.MULTIPLE_CHOICE, choices: { values: ['c1', 'c2', 'c3'] } }
    }
};

const renderResponse = (response: any) =>
    render(
        <ReduxProvider store={store}>
            <I18nProvider>
                <IndividualFormResponse formFields={formFields} response={response} form={form} />
            </I18nProvider>
        </ReduxProvider>
    );

describe('the respondent receipt view of a response', () => {
    beforeEach(() => {
        store.dispatch(setWorkspace({ id: 'workspace-1' } as any));
    });

    it('joins the options of a multi-select answer with ", "', () => {
        renderResponse(known);
        expect(screen.getByText('Anna Example')).toBeInTheDocument();
        expect(screen.getByText('Reading, Cycling, Cooking')).toBeInTheDocument();
        expect(screen.queryByText('Reading,Cycling,Cooking')).toBeNull();
    });

    it('joins a multi-select answer inside a repeating group with ", " too (not the export\'s "; ")', () => {
        const group = { id: 'g', type: FieldTypes.GROUP, title: 'Kids', properties: { repeat: { minItems: 1, maxItems: 3, itemLabel: 'Kid' }, fields: [{ ...formFields[1], id: 'k1' }] } };
        const answers = { g: { items: [{ k1: { field: { id: 'k1' }, type: FieldTypes.MULTIPLE_CHOICE, choices: { values: ['c1', 'c3'] } } }] } };
        render(
            <ReduxProvider store={store}>
                <I18nProvider>
                    <IndividualFormResponse formFields={[group as any]} response={{ ...known, answers } as any} form={{ ...form, fields: [group] }} />
                </I18nProvider>
            </ReduxProvider>
        );
        expect(screen.getByText('Reading, Cooking')).toBeInTheDocument();
        expect(screen.queryByText('Reading; Cooking')).toBeNull();
    });

    it('says once that the response could not be decrypted, and keeps the per-question text short', () => {
        renderResponse({ ...known, answers: {}, unreadableFields: ['answers'] });
        expect(screen.getAllByText('This response could not be decrypted')).toHaveLength(1);
        expect(screen.getAllByText('Could not be decrypted')).toHaveLength(2);
        expect(screen.queryByText('No answer')).toBeNull();
        // plain text: it is there on open, so a live region would announce nothing
        expect(screen.queryByRole('status')).toBeNull();
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it('still says "No answer" for a readable response that has no answer', () => {
        renderResponse({ ...known, answers: {} });
        expect(screen.getAllByText('No answer')).toHaveLength(2);
        expect(screen.queryByText(/could not be decrypted/i)).toBeNull();
    });

    it('names what could not be read when only hidden or staff data failed', () => {
        renderResponse({ ...known, unreadableFields: ['hidden_fields'] });
        expect(screen.getByText('Some data in this response could not be decrypted')).toBeInTheDocument();
        expect(screen.getByText(/hidden fields/)).toBeInTheDocument();
        expect(screen.getByText('Anna Example')).toBeInTheDocument();
        expect(screen.queryByText('Could not be decrypted')).toBeNull();
    });
});
