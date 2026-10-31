import React, { useEffect } from 'react';

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useClearUnavailableOptions, useOptionStates } from '@app/lib/hooks/use-option-states';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { resetSingleForm, setForm } from '@app/store/forms/slice';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { checkAnswerRules } from '@app/utils/answer-rules';
import { validateSlide } from '@app/utils/vvalidation-utils';

import DropDownField from './drop-down-field';
import MultipleChoiceField from './multiple-choice-field';
import MultipleChoiceWithMultipleSelection from './multiple-choice-with-multiple-selections';

// RenderImage drags in the whole builder field registry; irrelevant here.
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));

const COUNTRIES = [
    { id: 'c-nl', value: 'Netherlands' },
    { id: 'c-de', value: 'Germany' },
    { id: 'c-be', value: 'Belgium' }
];
const CITIES = [
    { id: 'ct-ams', value: 'Amsterdam' },
    { id: 'ct-rot', value: 'Rotterdam' },
    { id: 'ct-ber', value: 'Berlin' },
    { id: 'ct-bru', value: 'Brussels' }
];
const COUNTRY: StandardFormFieldDto = { id: 'country', index: 0, type: FieldTypes.DROP_DOWN, title: 'Country', properties: { choices: COUNTRIES } };
const CITY: StandardFormFieldDto = {
    id: 'city',
    index: 1,
    type: FieldTypes.MULTIPLE_CHOICE,
    title: 'City',
    properties: {
        choices: CITIES,
        optionFilter: {
            fieldId: 'country',
            mapping: [
                { when: 'c-nl', show: ['ct-ams', 'ct-rot'] },
                { when: 'c-de', show: ['ct-ber'] },
                { when: 'c-be', show: ['ct-bru'] }
            ]
        }
    }
};
const AGE: StandardFormFieldDto = { id: 'age', index: 2, type: FieldTypes.NUMBER, title: 'Age' };
const DRINK: StandardFormFieldDto = {
    id: 'drink',
    index: 3,
    type: FieldTypes.MULTIPLE_CHOICE,
    title: 'Drink',
    properties: {
        allowMultipleSelection: true,
        choices: [
            { id: 'soda', value: 'Soda' },
            { id: 'wine', value: 'Wine', logic: { action: 'SHOW', operator: 'AND' as any, conditions: [{ fieldId: 'age', fieldType: 'number', comparison: 'GREATER_THAN_EQUAL' as any, value: '18' }] } }
        ]
    }
};
const slide = (fields: StandardFormFieldDto[]) => ({ id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;
const WITH_LOGIC = [slide([COUNTRY, CITY, AGE, DRINK])];
const WITHOUT_LOGIC = [slide([COUNTRY, { ...CITY, properties: { choices: CITIES } }, AGE, { ...DRINK, properties: { allowMultipleSelection: true, choices: DRINK.properties!.choices!.map(({ logic: _logic, ...rest }) => rest) } }])];

function useOnFirstPage() {
    const { responderState, setResponderState } = useResponderState();
    useEffect(() => {
        setResponderState({ ...responderState, currentSlide: 0 });
    }, []);
}

/** A page as FormSlide builds it: the clearing hook, then the question controls. */
function Page({ fields }: { fields: StandardFormFieldDto[] }) {
    useOnFirstPage();
    useClearUnavailableOptions(store.getState().form.fields);
    const { addFieldChoiceAnswer, addFieldChoicesAnswer, addFieldNumberAnswer, formResponse } = useFormResponse();
    const options = useOptionStates();
    return (
        <>
            <button onClick={() => addFieldChoiceAnswer('country', 'c-nl')}>pick NL</button>
            <button onClick={() => addFieldChoiceAnswer('country', 'c-de')}>pick DE</button>
            <button onClick={() => addFieldChoiceAnswer('city', 'ct-ams')}>pick Amsterdam</button>
            <button onClick={() => addFieldNumberAnswer('age', 20)}>age 20</button>
            <button onClick={() => addFieldNumberAnswer('age', 10)}>age 10</button>
            <button onClick={() => addFieldChoicesAnswer('drink', ['soda', 'wine'])}>drink both</button>
            <output data-testid="answers">{JSON.stringify(formResponse.answers ?? {})}</output>
            <output data-testid="none-left">{[...options.noneLeft].join(',')}</output>
            <DropDownField field={fields[0]} slideIndex={0} />
            <MultipleChoiceField field={fields[1]} slideIndex={0} />
            <MultipleChoiceWithMultipleSelection field={fields[3]} slideIndex={0} />
        </>
    );
}

const renderPage = (slides: StandardFormFieldDto[]) => {
    store.dispatch(setForm({ title: 'Form', fields: slides }));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Page fields={slides[0].properties!.fields!} />
            </Provider>
        </ReduxProvider>
    );
};

const answers = () => JSON.parse(screen.getByTestId('answers').textContent ?? '{}');
const radios = () => screen.queryAllByRole('radio').map((radio) => radio.textContent);
const checkboxes = () => screen.queryAllByRole('checkbox').map((box) => box.textContent);

describe('option logic on the respondent page', () => {
    beforeEach(() => {
        store.dispatch(resetSingleForm());
        window.history.replaceState(null, '', '/');
    });
    afterEach(cleanup);

    it('offers every option until the earlier question is answered, then only the ones it maps to', async () => {
        renderPage(WITH_LOGIC);
        expect(radios()).toEqual(['Amsterdam', 'Rotterdam', 'Berlin', 'Brussels']);
        await act(async () => fireEvent.click(screen.getByText('pick NL')));
        expect(radios()).toEqual(['Amsterdam', 'Rotterdam']);
        await act(async () => fireEvent.click(screen.getByText('pick DE')));
        expect(radios()).toEqual(['Berlin']);
    });

    it('offers an option only while its own conditions hold (checkboxes)', async () => {
        renderPage(WITH_LOGIC);
        expect(checkboxes()).toEqual(['Soda']);
        await act(async () => fireEvent.click(screen.getByText('age 20')));
        expect(checkboxes()).toEqual(['Soda', 'Wine']);
        await act(async () => fireEvent.click(screen.getByText('age 10')));
        expect(checkboxes()).toEqual(['Soda']);
    });

    it('offers a dropdown only the options that are available', async () => {
        const filteredDropdown: StandardFormFieldDto = { ...CITY, id: 'town', type: FieldTypes.DROP_DOWN, title: 'Town', properties: { ...CITY.properties, optionFilter: { fieldId: 'country', mapping: [{ when: 'c-nl', show: ['ct-ams'] }] } } };
        const slides = [slide([COUNTRY, filteredDropdown])];
        store.dispatch(setForm({ title: 'Form', fields: slides }));
        function DropdownPage() {
            useOnFirstPage();
            const { addFieldChoiceAnswer } = useFormResponse();
            return (
                <>
                    <button onClick={() => addFieldChoiceAnswer('country', 'c-nl')}>pick NL</button>
                    <DropDownField field={filteredDropdown} slideIndex={0} />
                </>
            );
        }
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <DropdownPage />
                </Provider>
            </ReduxProvider>
        );
        await act(async () => fireEvent.click(screen.getByText('pick NL')));
        await act(async () => fireEvent.click(screen.getByRole('button', { name: /Select an option|Town/ })));
        expect(screen.queryByText('Berlin')).not.toBeInTheDocument();
        expect(screen.getByText('Amsterdam')).toBeInTheDocument();
        expect(screen.queryByText('Rotterdam')).not.toBeInTheDocument();
    });

    it('clears a selection that stops being available and says so politely, until it is answered again', async () => {
        renderPage(WITH_LOGIC);
        await act(async () => fireEvent.click(screen.getByText('pick NL')));
        await act(async () => fireEvent.click(screen.getByText('pick Amsterdam')));
        expect(answers().city).toMatchObject({ type: 'choice', choice: { value: 'ct-ams' } });
        const status = screen.getByTestId('option-cleared-city');
        // the region is in the page before it has anything to say, and polite
        expect(status.getAttribute('role')).toBe('status');
        expect(status.getAttribute('aria-live')).toBe('polite');
        expect(status.textContent).toBe('');

        await act(async () => fireEvent.click(screen.getByText('pick DE')));
        expect(answers().city).toBeUndefined();
        expect(answers().country.choice.value).toBe('c-de');
        expect(screen.getByTestId('option-cleared-city').textContent).toBe('“Amsterdam” is no longer available, so it was removed from your answer. Please check your answer.');
        // the same node, so a screen reader announces the new text
        expect(screen.getByTestId('option-cleared-city')).toBe(status);

        // answering again takes the notice away
        await act(async () => fireEvent.click(screen.getByRole('radio', { name: 'Berlin' })));
        expect(answers().city.choice.value).toBe('ct-ber');
        expect(screen.getByTestId('option-cleared-city').textContent).toBe('');
    });

    it('removes only the unavailable options of a multiple choice', async () => {
        renderPage(WITH_LOGIC);
        await act(async () => fireEvent.click(screen.getByText('age 20')));
        await act(async () => fireEvent.click(screen.getByText('drink both')));
        expect(answers().drink.choices.values).toEqual(['soda', 'wine']);
        await act(async () => fireEvent.click(screen.getByText('age 10')));
        expect(answers().drink.choices.values).toEqual(['soda']);
        expect(screen.getByTestId('option-cleared-drink').textContent).toContain('“Wine” is no longer available');
    });

    it('says it in Dutch with ?lang=nl', async () => {
        window.history.replaceState(null, '', '/?lang=nl');
        renderPage(WITH_LOGIC);
        await act(async () => fireEvent.click(screen.getByText('pick NL')));
        await act(async () => fireEvent.click(screen.getByText('pick Amsterdam')));
        await act(async () => fireEvent.click(screen.getByText('pick DE')));
        expect(screen.getByTestId('option-cleared-city').textContent).toBe('“Amsterdam” is niet meer beschikbaar en is uit je antwoord gehaald. Controleer je antwoord.');
    });

    it('leaves a form without option logic alone: nothing hidden, nothing cleared, no notice text', async () => {
        renderPage(WITHOUT_LOGIC);
        await act(async () => fireEvent.click(screen.getByText('pick NL')));
        await act(async () => fireEvent.click(screen.getByText('pick Amsterdam')));
        expect(radios()).toEqual(['Amsterdam', 'Rotterdam', 'Berlin', 'Brussels']);
        await act(async () => fireEvent.click(screen.getByText('pick DE')));
        expect(answers().city.choice.value).toBe('ct-ams');
        expect(screen.getByTestId('option-cleared-city').textContent).toBe('');
    });

    it('never requires a question with nothing to choose, and holds a minimum to what is offered', async () => {
        const required: StandardFormFieldDto = { ...CITY, validations: { required: true }, properties: { ...CITY.properties, optionFilter: { fieldId: 'country', mapping: [{ when: 'c-nl', show: ['ct-ams'] }] } } };
        const slides = [slide([COUNTRY, required])];
        store.dispatch(setForm({ title: 'Form', fields: slides }));
        const given = { country: { type: 'choice', choice: { value: 'c-de' } } };
        const { optionStatesFor } = await import('@app/lib/hooks/use-option-states');
        const states = optionStatesFor(store.getState().form.fields, given, [0], new Set());
        expect(states.isNoneLeft('city')).toBe(true);
        expect(validateSlide(slides[0], given, undefined, states)).toEqual({});
        // without the option states the static flag decides
        expect(validateSlide(slides[0], given)).toEqual({ city: [0] });

        const several: StandardFormFieldDto = { ...DRINK, validations: { minChoices: 2 } };
        const offered = optionStatesFor([slide([AGE, several])], { age: { type: 'number', number: 10 } }, [0], new Set());
        const picked = { type: 'choices', choices: { values: ['soda'] } };
        expect(checkAnswerRules(several, picked, offered)).toEqual([]);
        expect(checkAnswerRules(several, picked)).toEqual(['TOO_FEW_CHOICES']);
    });
});
