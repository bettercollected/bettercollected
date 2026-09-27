import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { store } from '@app/store/store';
import InputField from './input-field';
import RepeatingGroupField from './repeating-group-field';

const group = (repeat: Record<string, any> = {}): StandardFormFieldDto => ({
    id: 'g',
    index: 0,
    type: FieldTypes.GROUP,
    title: 'Applicants',
    properties: {
        repeat: { minItems: 1, maxItems: 2, itemLabel: 'Applicant', itemTitle: '{{field:name}}', ...repeat },
        fields: [{ id: 'name', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name', properties: { placeholder: 'Full name' } }]
    }
});

let latestAnswers: Record<string, any> = {};
const Probe = () => {
    const { formResponse } = useFormResponse();
    latestAnswers = formResponse.answers;
    return null;
};

const renderGroup = (field: StandardFormFieldDto) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <RepeatingGroupField field={field} renderChild={(child) => <InputField field={child} />} />
                <Probe />
            </Provider>
        </ReduxProvider>
    );

describe('RepeatingGroupField', () => {
    it('starts with the minimum, adds up to the maximum and answers into each item', async () => {
        renderGroup(group());
        expect(screen.getByRole('heading', { name: 'Applicant 1' })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Remove/ })).not.toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText('Full name'), { target: { value: 'Sita' } });
        // Inputs are debounced (300ms) before they reach the answers.
        expect(await screen.findByRole('heading', { name: 'Applicant 1: Sita' }, { timeout: 2000 })).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Add another Applicant' }));
        const inputs = screen.getAllByPlaceholderText('Full name');
        expect(inputs).toHaveLength(2);
        fireEvent.change(inputs[1], { target: { value: 'Ram' } });

        await waitFor(() => expect(latestAnswers.g.items.map((item: any) => item.name?.text)).toEqual(['Sita', 'Ram']), { timeout: 2000 });
        // Answers never leak to the top level under the child id.
        expect(latestAnswers.name).toBeUndefined();
        // At the maximum the add button is disabled; above the minimum, remove appears.
        expect(screen.getByRole('button', { name: 'Add another Applicant' })).toBeDisabled();
        fireEvent.click(screen.getByRole('button', { name: 'Remove Applicant 1: Sita' }));
        expect(latestAnswers.g.items.map((item: any) => item.name?.text)).toEqual(['Ram']);
        expect(await screen.findByRole('heading', { name: 'Applicant 1: Ram' })).toBeInTheDocument();
    });

    it('offers "Add <label>" when no item is required', () => {
        renderGroup(group({ minItems: 0 }));
        expect(screen.queryByRole('heading', { name: /Applicant 1/ })).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Add Applicant' }));
        expect(screen.getByRole('heading', { name: 'Applicant 1' })).toBeInTheDocument();
    });
});
