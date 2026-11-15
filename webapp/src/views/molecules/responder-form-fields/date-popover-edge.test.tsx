// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';

import DateField from './date-field';
import DateRangeField from './date-range-field';

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

// The calendar of a date question opens in a popover that Radix portals to <body>: outside the form root, so a Pigment
// workspace's preview would draw its edge from `<html>`, where the real page is on the frozen ramp. The two call sites
// therefore name the frozen edge, and this holds them to it.
const date: StandardFormFieldDto = { id: 'when', index: 0, type: FieldTypes.DATE, title: 'When do you leave?', properties: {} };
const range: StandardFormFieldDto = { id: 'stay', index: 1, type: FieldTypes.DATE_RANGE, title: 'When do you stay?', properties: {} };

const show = (field: StandardFormFieldDto, Component: React.ComponentType<{ field: StandardFormFieldDto }>) => {
    store.dispatch(setForm({ formId: 'f', title: 'Trip', fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [date, range] } }] }));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Component field={field} />
            </Provider>
        </ReduxProvider>
    );
};

describe('the calendar popover of the date questions', () => {
    it.each([
        ['a date', date, DateField],
        ['a date range', range, DateRangeField]
    ])('draws the edge of %s on the frozen ramp, not on the app role', (_name, field, Component) => {
        show(field, Component as React.ComponentType<{ field: StandardFormFieldDto }>);
        fireEvent.click(screen.getAllByRole('button')[0]);
        const popover = screen.getByRole('dialog');
        expect(popover.className).toContain('border-black-300');
        expect(popover.className).not.toContain('border-app-edge');
    });
});
