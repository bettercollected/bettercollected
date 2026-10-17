import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import FieldDescription from '@app/views/organism/form-builder/fields/field-description';

import useFormFieldsAtom, { UNDO_COALESCE_MS } from './field-selectors';

const page = (): StandardFormFieldDto[] => [
    {
        id: 'page-1',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: {
            fields: [
                { id: 'q-1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name', description: '' },
                { id: 'q-2', index: 1, type: FieldTypes.SHORT_TEXT, title: 'Email', description: '' }
            ]
        }
    } as StandardFormFieldDto
];

let builder: ReturnType<typeof useFormFieldsAtom>;

function Builder({ withDescription = false }: { withDescription?: boolean }) {
    builder = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    React.useEffect(() => {
        builder.initFormFields(page());
        setActiveSlideComponent({ id: 'page-1', index: 0 });
    }, []);
    const field = builder.formFields[0]?.properties?.fields?.[0];
    return withDescription && field && builder.activeSlide ? <FieldDescription field={field} /> : null;
}

const description = (fieldIndex = 0) => builder.formFields[0].properties!.fields![fieldIndex].description;
const type = async (text: string, fieldIndex = 0) => {
    await act(async () => builder.updateDescription(fieldIndex, 0, text));
    vi.advanceTimersByTime(150);
};

describe('undo while typing', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        render(
            <Provider>
                <Builder />
            </Provider>
        );
    });
    afterEach(() => vi.useRealTimers());

    it('one run of typing in a description is one undo step', async () => {
        for (const text of ['Y', 'Yo', 'You', 'Your', 'Your n', 'Your name']) await type(text);
        expect(description()).toBe('Your name');
        await act(async () => builder.undo());
        expect(description()).toBe('');
        expect(builder.canUndo).toBe(false);
        await act(async () => builder.redo());
        expect(description()).toBe('Your name');
    });

    it('a pause starts a new step', async () => {
        await type('Your');
        vi.advanceTimersByTime(UNDO_COALESCE_MS);
        await type('Your name');
        await act(async () => builder.undo());
        expect(description()).toBe('Your');
        await act(async () => builder.undo());
        expect(description()).toBe('');
    });

    it('edits of another field or another property are their own steps', async () => {
        await type('first');
        await type('second', 1);
        await act(async () => builder.updateFieldPlaceholder(1, 0, 'you@example.org'));
        await act(async () => builder.undo());
        expect(builder.formFields[0].properties!.fields![1].properties?.placeholder).toBeUndefined();
        expect(description(1)).toBe('second');
        await act(async () => builder.undo());
        expect(description(1)).toBe('');
        expect(description()).toBe('first');
        await act(async () => builder.undo());
        expect(description()).toBe('');
    });

    it('other changes are never merged', async () => {
        await act(async () => builder.updateFieldRequired(0, 0, true));
        await act(async () => builder.updateFieldRequired(0, 0, false));
        await act(async () => builder.undo());
        expect(builder.formFields[0].properties!.fields![0].validations?.required).toBe(true);
    });

    it('typing after an undo starts a new step instead of rewriting an old one', async () => {
        await type('abc');
        await act(async () => builder.undo());
        await type('xyz');
        expect(builder.canRedo).toBe(false);
        await act(async () => builder.undo());
        expect(description()).toBe('');
    });
});

describe('question description', () => {
    it('shows the stored value after an undo (it is never a stale copy)', async () => {
        render(
            <Provider>
                <Builder withDescription />
            </Provider>
        );
        const box = await screen.findByLabelText('Question description');
        fireEvent.change(box, { target: { value: 'Typed' } });
        expect((box as HTMLTextAreaElement).value).toBe('Typed');
        await act(async () => builder.undo());
        expect((screen.getByLabelText('Question description') as HTMLTextAreaElement).value).toBe('');
    });
});
