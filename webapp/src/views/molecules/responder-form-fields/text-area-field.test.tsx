import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
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
import TextAreaField from './text-area-field';

const field: StandardFormFieldDto = { id: 'q', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name', properties: { placeholder: 'Your name' } };

let latestAnswers: Record<string, any> = {};
const Probe = () => {
    const { formResponse } = useFormResponse();
    latestAnswers = formResponse.answers;
    return null;
};

describe('TextAreaField', () => {
    it('commits the answer as soon as the field loses focus, without waiting for the debounce', () => {
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <TextAreaField field={field} />
                    <Probe />
                </Provider>
            </ReduxProvider>
        );
        const input = screen.getByPlaceholderText('Your name');
        fireEvent.change(input, { target: { value: 'Hari' } });
        expect(latestAnswers.q).toBeUndefined(); // still debounced
        fireEvent.blur(input);
        expect(latestAnswers.q?.text).toBe('Hari');
    });
});
