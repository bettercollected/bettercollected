import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { setForm } from '@app/store/forms/slice';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { store } from '@app/store/store';

import DateField from './date-field';

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const start: StandardFormFieldDto = { id: 'start', index: 0, type: FieldTypes.DATE, title: 'When do you leave?', properties: { label: 'Start date' } };
const end: StandardFormFieldDto = { id: 'end', index: 1, type: FieldTypes.DATE, title: 'When are you back?', properties: { dateRules: [{ comparison: 'after', target: 'field', fieldId: 'start' }] } };

const renderField = (field: StandardFormFieldDto, answers: Record<string, any>, isBuilder = false) => {
    store.dispatch(setForm({ formId: 'f', title: 'Trip', fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [start, end] } }] }));
    const Harness = () => {
        const { setFormResponse, formResponse } = useFormResponse();
        const [ready, setReady] = React.useState(false);
        React.useEffect(() => {
            setFormResponse({ ...formResponse, answers });
            setReady(true);
            // eslint-disable-next-line react-hooks/exhaustive-deps
        }, []);
        return ready ? <DateField field={field} isBuilder={isBuilder} /> : null;
    };
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Harness />
            </Provider>
        </ReduxProvider>
    );
};

describe('DateField', () => {
    it('shows the label with the picker, in the form and on the builder canvas', () => {
        renderField(start, {});
        expect(screen.getByLabelText('Start date')).toHaveTextContent('Pick a date');
        renderField(start, {}, true);
        expect(screen.getAllByText('Start date')).toHaveLength(2);
    });

    it('explains a date that breaks a rule, using the other date', () => {
        renderField(end, { start: { type: 'date', date: '2026-03-12' }, end: { type: 'date', date: '2026-03-10' } });
        expect(screen.getByRole('alert')).toHaveTextContent('Must be after Start date (12 Mar 2026).');
    });

    it('shows the chosen calendar day, not the UTC one', () => {
        renderField(end, { end: { type: 'date', date: '2026-03-10' } });
        expect(screen.getByText('March 10th, 2026')).toBeInTheDocument();
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
});
