import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useField, usePage } from '@app/store/jotai/entity-hooks';
import { resetFromServerAtom } from '@app/store/jotai/form-document';

import DropDownField from './drop-down-field';

const loadedForm = () => ({
    formId: 'form-1',
    title: 'Choices',
    fields: [
        {
            id: 'page-1',
            index: 0,
            type: FieldTypes.SLIDE,
            properties: {
                fields: [
                    {
                        id: 'q-1',
                        index: 0,
                        type: FieldTypes.MULTIPLE_CHOICE,
                        title: 'Pick one',
                        properties: {
                            choices: [
                                { id: 'c-1', value: 'Red' },
                                { id: 'c-2', value: 'Green' },
                                { id: 'c-3', value: 'Blue' }
                            ]
                        }
                    }
                ]
            }
        }
    ]
});

/** The question as the canvas shows it: it follows its own question in the document. */
function Question() {
    const page = usePage('page-1');
    const field = useField('q-1');
    if (!page || !field) return null;
    return <DropDownField field={field as StandardFormFieldDto} slide={page as StandardFormFieldDto} disabled={false} />;
}

/** The question on a builder that has just loaded the form. */
function renderQuestion() {
    const store = createStore();
    store.set(resetFromServerAtom, loadedForm() as any);
    render(
        <Provider store={store}>
            <Question />
        </Provider>
    );
}

const optionInputs = () => screen.getAllByPlaceholderText(/^Item \d+$/) as HTMLInputElement[];

describe('the choices of a question in the builder', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it('Add Option adds an empty row and puts the cursor in it', async () => {
        renderQuestion();
        await act(async () => vi.advanceTimersByTimeAsync(0));
        expect(optionInputs()).toHaveLength(3);

        fireEvent.click(screen.getByRole('button', { name: 'Add Option' }));
        await act(async () => vi.advanceTimersByTimeAsync(0));

        const inputs = optionInputs();
        expect(inputs).toHaveLength(4);
        expect(inputs[3].value).toBe('');
        expect(document.activeElement).toBe(inputs[3]);
    });

    it('removing an option right after typing in another keeps what was typed', async () => {
        renderQuestion();
        await act(async () => vi.advanceTimersByTimeAsync(0));

        // Typed in the last option, then the first is removed before the typing is saved.
        fireEvent.change(optionInputs()[2], { target: { value: 'Blue sky' } });
        await act(async () => vi.advanceTimersByTimeAsync(100));
        fireEvent.click(screen.getByRole('button', { name: 'Remove option 1: Red' }));
        await act(async () => vi.advanceTimersByTimeAsync(1000));

        expect(optionInputs().map((input) => input.value)).toEqual(['Green', 'Blue sky']);
    });
});
