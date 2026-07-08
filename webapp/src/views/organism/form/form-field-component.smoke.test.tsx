import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

// RenderImage drags in the whole builder field registry — irrelevant here.
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { store } from '@app/store/store';
import { FormFieldComponent } from './form-slide';

/**
 * Render-crash smoke test for every field type the responder runtime can
 * show, through the exact production mapping (FormFieldComponent). A field
 * type that throws while rendering — undefined property access, a bad hook,
 * a broken import — fails here before anyone finds it on a live form
 * (the yes/no field regression is what prompted this net).
 */

const base = (type: FieldTypes, overrides: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({
    id: `field-${type}`,
    index: 0,
    type,
    title: `Question for ${type}`,
    ...overrides
});

const choices = (...values: string[]) => values.map((value, i) => ({ id: `choice-${i}`, value }));

const FIELDS: Array<{ name: string; field: StandardFormFieldDto }> = [
    { name: 'text (statement)', field: base(FieldTypes.TEXT) },
    { name: 'short_text', field: base(FieldTypes.SHORT_TEXT) },
    { name: 'long_text', field: base(FieldTypes.LONG_TEXT) },
    { name: 'email', field: base(FieldTypes.EMAIL) },
    { name: 'number', field: base(FieldTypes.NUMBER) },
    { name: 'url', field: base(FieldTypes.LINK) },
    { name: 'phone_number', field: base(FieldTypes.PHONE_NUMBER) },
    { name: 'date', field: base(FieldTypes.DATE) },
    { name: 'yes_no', field: base(FieldTypes.YES_NO, { properties: { fields: [], choices: choices('Yes', 'No') } }) },
    { name: 'multiple_choice (single)', field: base(FieldTypes.MULTIPLE_CHOICE, { properties: { fields: [], choices: choices('Red', 'Green', 'Blue') } }) },
    { name: 'multiple_choice (multi-select)', field: base(FieldTypes.MULTIPLE_CHOICE, { properties: { fields: [], choices: choices('Red', 'Green', 'Blue'), allowMultipleSelection: true } }) },
    { name: 'dropdown', field: base(FieldTypes.DROP_DOWN, { properties: { fields: [], choices: choices('One', 'Two') } }) },
    { name: 'rating', field: base(FieldTypes.RATING, { properties: { fields: [], steps: 5 } }) },
    { name: 'linear_rating', field: base(FieldTypes.LINEAR_RATING, { properties: { fields: [], steps: 10 } }) },
    { name: 'file_upload', field: base(FieldTypes.FILE_UPLOAD) },
    {
        name: 'matrix',
        field: base(FieldTypes.MATRIX, {
            properties: {
                fields: [
                    { id: 'row-1', index: 0, type: FieldTypes.MATRIX_ROW_INPUT, title: 'Quality', properties: { fields: [], choices: choices('Poor', 'Great') } },
                    { id: 'row-2', index: 1, type: FieldTypes.MATRIX_ROW_INPUT, title: 'Speed', properties: { fields: [], choices: choices('Poor', 'Great') } }
                ]
            }
        })
    },
    { name: 'tabular_input', field: base(FieldTypes.TABULAR_INPUT, { properties: { fields: [], rowTitles: ['Row 1', 'Row 2'], columnTitles: ['Name', 'Amount'] } }) },
    { name: 'image_content', field: base(FieldTypes.IMAGE_CONTENT, { attachment: { href: 'https://example.com/picture.png' } as any }) },
    { name: 'video_content', field: base(FieldTypes.VIDEO_CONTENT, { attachment: { href: 'www.youtube.com/watch?v=abc123' } as any }) }
];

const renderField = (field: StandardFormFieldDto) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <FormFieldComponent field={field} slideIndex={0} />
            </Provider>
        </ReduxProvider>
    );

describe('FormFieldComponent renders every responder field type without crashing', () => {
    it.each(FIELDS)('$name', ({ field }) => {
        const { container } = renderField(field);
        expect(container.firstChild).not.toBeNull();
    });

    it('a field with NO properties at all still renders (legacy/imported forms)', () => {
        // Imported or hand-migrated forms can carry fields with missing
        // properties — the runtime must degrade, not crash.
        for (const type of [FieldTypes.YES_NO, FieldTypes.MULTIPLE_CHOICE, FieldTypes.DROP_DOWN, FieldTypes.MATRIX, FieldTypes.TABULAR_INPUT, FieldTypes.RATING, FieldTypes.LINEAR_RATING]) {
            const { container } = renderField(base(type));
            expect(container.firstChild).not.toBeNull();
        }
    });
});
