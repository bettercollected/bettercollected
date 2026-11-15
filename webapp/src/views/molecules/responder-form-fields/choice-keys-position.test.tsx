import React, { useEffect } from 'react';

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FormTheme } from '@app/constants/theme';
import { useClearUnavailableOptions } from '@app/lib/hooks/use-option-states';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { resetSingleForm, setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { CHOICE_KEY_FILLS } from '@app/views/atoms/choice';

import MultipleChoiceField from './multiple-choice-field';
import MultipleChoiceWithMultipleSelection from './multiple-choice-with-multiple-selections';

// RenderImage drags in the whole builder field registry; irrelevant here.
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));

/**
 * The key letter and the pigment of an option are its place among the options
 * SHOWN, so they keep step when option logic hides some: with the first option
 * hidden, the first one shown is A in the first pigment.
 */

const LETTERED: FormTheme = { title: 'Lettered', primary: '#1A1238', secondary: '#4B35DB', tertiary: '#7C7396', accent: '#FBF7F1', choiceKeys: 'letters' };

const AGE: StandardFormFieldDto = { id: 'age', index: 0, type: FieldTypes.NUMBER, title: 'Age' };
const adult = { action: 'SHOW', operator: 'AND' as any, conditions: [{ fieldId: 'age', fieldType: 'number', comparison: 'GREATER_THAN_EQUAL' as any, value: '18' }] };
// the first option is the one the logic hides until the age is known
const DRINK: StandardFormFieldDto = {
    id: 'drink',
    index: 1,
    type: FieldTypes.MULTIPLE_CHOICE,
    title: 'Drink',
    properties: {
        allowMultipleSelection: true,
        choices: [
            { id: 'wine', value: 'Wine', logic: adult },
            { id: 'soda', value: 'Soda' },
            { id: 'water', value: 'Water' }
        ]
    }
};
// one option is shown only for an age of 18 or more, the others always
const PICK: StandardFormFieldDto = {
    id: 'pick',
    index: 2,
    type: FieldTypes.MULTIPLE_CHOICE,
    title: 'Pick',
    properties: {
        choices: [
            { id: 'beer', value: 'Beer', logic: adult },
            { id: 'tea', value: 'Tea' },
            { id: 'milk', value: 'Milk' }
        ]
    }
};
const slide = (fields: StandardFormFieldDto[]) => ({ id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;
const SLIDES = [slide([AGE, DRINK, PICK])];

function Page() {
    const { responderState, setResponderState } = useResponderState();
    const { updateFormTheme } = useFormState();
    const [ready, setReady] = React.useState(false);
    useEffect(() => {
        setResponderState({ ...responderState, currentSlide: 0 });
        updateFormTheme(LETTERED as any, { undoable: false });
        setReady(true);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    useClearUnavailableOptions(store.getState().form.fields);
    const { addFieldNumberAnswer } = useFormResponse();
    return (
        <>
            <button onClick={() => addFieldNumberAnswer('age', 20)}>age 20</button>
            {ready && (
                <>
                    <MultipleChoiceWithMultipleSelection field={DRINK} slideIndex={0} />
                    <MultipleChoiceField field={PICK} slideIndex={0} />
                </>
            )}
        </>
    );
}

const renderPage = () => {
    store.dispatch(setForm({ title: 'Form', fields: SLIDES }));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Page />
            </Provider>
        </ReduxProvider>
    );
};

const hex = (value: string) => {
    const channels = [1, 3, 5].map((start) => parseInt(value.slice(start, start + 2), 16));
    return `rgb(${channels.join(', ')})`;
};

/** The letters and the pigments of the keys shown in a group of options, in order. */
const keysIn = (container: HTMLElement, role: 'checkbox' | 'radio') =>
    Array.from(container.querySelectorAll<HTMLElement>(`[role="${role}"] [data-choice-key]`)).map((key) => ({ letter: key.textContent, background: key.style.background }));

describe('the key letters and pigments of the options shown', () => {
    beforeEach(() => {
        store.dispatch(resetSingleForm());
        window.history.replaceState(null, '', '/');
    });
    afterEach(cleanup);

    it('start at A in the first pigment when the first option is hidden (checkboxes)', async () => {
        const { container } = renderPage();
        await screen.findByText('Soda');
        expect(screen.queryByText('Wine')).toBeNull();
        expect(keysIn(container, 'checkbox')).toEqual([
            { letter: 'A', background: hex(CHOICE_KEY_FILLS[0]) },
            { letter: 'B', background: hex(CHOICE_KEY_FILLS[1]) }
        ]);
        // the shown ones carry the letters that choose them
        expect(screen.getByText('Soda').closest('button')?.getAttribute('data-option-key')).toBe('A');
        expect(screen.getByText('Water').closest('button')?.getAttribute('data-option-key')).toBe('B');
    });

    it('move on together when the hidden option comes back (checkboxes)', async () => {
        const { container } = renderPage();
        await screen.findByText('Soda');
        await act(async () => fireEvent.click(screen.getByText('age 20')));
        expect(await screen.findByText('Wine')).toBeTruthy();
        expect(keysIn(container, 'checkbox')).toEqual([
            { letter: 'A', background: hex(CHOICE_KEY_FILLS[0]) },
            { letter: 'B', background: hex(CHOICE_KEY_FILLS[1]) },
            { letter: 'C', background: hex(CHOICE_KEY_FILLS[2]) }
        ]);
        expect(screen.getByText('Wine').closest('button')?.getAttribute('data-option-key')).toBe('A');
    });

    it('do the same for a single answer (radios)', async () => {
        const { container } = renderPage();
        await screen.findByText('Tea');
        expect(screen.queryByText('Beer')).toBeNull();
        expect(keysIn(container, 'radio')).toEqual([
            { letter: 'A', background: hex(CHOICE_KEY_FILLS[0]) },
            { letter: 'B', background: hex(CHOICE_KEY_FILLS[1]) }
        ]);
    });
});
