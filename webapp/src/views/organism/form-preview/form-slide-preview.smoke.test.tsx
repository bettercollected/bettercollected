import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { store } from '@app/store/store';
import FormSlidePreview from './form-slide-preview';

/**
 * The dashboard preview path (FormSlidePreview -> SlideLayoutWrapper ->
 * FormFieldComponent) with NOTHING mocked — the responder smoke test mocks the
 * builder field registry, which is exactly where a preview-only crash hides
 * (found the hard way with the kitchen-sink form).
 */

const choices = (...values: string[]) => values.map((value, i) => ({ id: `choice-${i}`, value }));

const f = (type: FieldTypes, index: number, overrides: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({
    id: `field-${type}-${index}`,
    index,
    type,
    title: `Question for ${type}`,
    ...overrides
});

const SLIDES: StandardFormFieldDto[] = [
    {
        id: 'slide-basics',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: {
            fields: [
                f(FieldTypes.SHORT_TEXT, 0),
                f(FieldTypes.LONG_TEXT, 1),
                f(FieldTypes.EMAIL, 2),
                f(FieldTypes.NUMBER, 3),
                f(FieldTypes.LINK, 4),
                f(FieldTypes.PHONE_NUMBER, 5),
                f(FieldTypes.DATE, 6)
            ]
        }
    },
    {
        id: 'slide-choices',
        index: 1,
        type: FieldTypes.SLIDE,
        properties: {
            fields: [
                f(FieldTypes.YES_NO, 0, { properties: { fields: [], choices: choices('Yes', 'No') } }),
                f(FieldTypes.MULTIPLE_CHOICE, 1, { properties: { fields: [], choices: choices('Red', 'Green', 'Blue') } }),
                f(FieldTypes.MULTIPLE_CHOICE, 2, { properties: { fields: [], choices: choices('Docs', 'Design'), allowMultipleSelection: true } }),
                f(FieldTypes.DROP_DOWN, 3, { properties: { fields: [], choices: choices('One', 'Two') } }),
                f(FieldTypes.RATING, 4, { properties: { fields: [], steps: 5 } }),
                f(FieldTypes.LINEAR_RATING, 5, { properties: { fields: [], steps: 10 } })
            ]
        }
    },
    {
        id: 'slide-rich',
        index: 2,
        type: FieldTypes.SLIDE,
        properties: {
            fields: [
                f(FieldTypes.TEXT, 0),
                f(FieldTypes.MATRIX, 1, {
                    properties: {
                        fields: [
                            { id: 'row-1', index: 0, type: FieldTypes.MATRIX_ROW_INPUT, title: 'Quality', properties: { fields: [], choices: choices('Poor', 'Great') } },
                            { id: 'row-2', index: 1, type: FieldTypes.MATRIX_ROW_INPUT, title: 'Speed', properties: { fields: [], choices: choices('Poor', 'Great') } }
                        ]
                    }
                }),
                f(FieldTypes.TABULAR_INPUT, 2, { properties: { fields: [], rowTitles: ['Item 1'], columnTitles: ['Name', 'Amount'] } }),
                f(FieldTypes.FILE_UPLOAD, 3),
                f(FieldTypes.IMAGE_CONTENT, 4, { attachment: { href: 'https://example.com/picture.png' } as any }),
                f(FieldTypes.VIDEO_CONTENT, 5, { attachment: { href: 'www.youtube.com/watch?v=abc123' } as any })
            ]
        }
    }
];

describe('FormSlidePreview renders every kitchen-sink slide without crashing', () => {
    it.each(SLIDES.map((slide) => ({ name: slide.id, slide })))('$name', ({ slide }) => {
        const { container } = render(
            <ReduxProvider store={store}>
                <Provider>
                    <FormSlidePreview slide={slide} />
                </Provider>
            </ReduxProvider>
        );
        expect(container.firstChild).not.toBeNull();
    });
});
