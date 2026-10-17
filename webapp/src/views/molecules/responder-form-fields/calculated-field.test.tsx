// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { useCalculatedFields } from '@app/lib/hooks/use-calculated-fields';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { store } from '@app/store/store';
import CalculatedField from '@app/views/molecules/responder-form-fields/calculated-field';

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));

const QTY: StandardFormFieldDto = { id: 'qty', index: 0, type: FieldTypes.NUMBER, title: 'Quantity' };
const TOTAL: StandardFormFieldDto = {
    id: 'total',
    index: 1,
    type: FieldTypes.CALCULATED,
    title: 'Total',
    properties: { expression: { '*': [{ var: 'qty' }, 12.5] }, format: { style: 'currency', decimals: 2 } }
};
const SLIDES = [{ id: 'p', index: 0, type: FieldTypes.SLIDE, properties: { fields: [QTY, TOTAL] } }] as StandardFormFieldDto[];

function Respondent() {
    useCalculatedFields(SLIDES);
    const { addFieldNumberAnswer, removeAnswer } = useFormResponse();
    return (
        <>
            <button onClick={() => addFieldNumberAnswer('qty', 3)}>three</button>
            <button onClick={() => addFieldNumberAnswer('qty', 4)}>four</button>
            <button onClick={() => removeAnswer('qty')}>clear</button>
            <CalculatedField field={TOTAL} slides={SLIDES} />
        </>
    );
}

const renderRespondent = () =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Respondent />
            </Provider>
        </ReduxProvider>
    );

describe('a calculated field for respondents', () => {
    it('updates live as answers change, in a labelled polite live region', async () => {
        renderRespondent();
        const output = screen.getByTestId('calculated-value');
        expect(output.getAttribute('aria-live')).toBe('polite');
        expect(output.getAttribute('aria-labelledby')).toContain('q-title-total');
        expect(output.textContent).toBe('Not calculated yet');
        await act(async () => fireEvent.click(screen.getByText('three')));
        expect(output.textContent).toBe('€37.50');
        await act(async () => fireEvent.click(screen.getByText('four')));
        expect(output.textContent).toBe('€50.00');
        await act(async () => fireEvent.click(screen.getByText('clear')));
        expect(output.textContent).toBe('Not calculated yet');
    });

    it('names the value "Calculation" when the field has no title', () => {
        const untitled = { ...TOTAL, title: '' };
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <CalculatedField field={untitled} slides={SLIDES} />
                </Provider>
            </ReduxProvider>
        );
        const output = screen.getByTestId('calculated-value');
        expect(output.getAttribute('aria-labelledby')).toBeNull();
        expect(output.getAttribute('aria-label')).toBe('Calculation');
    });
});
