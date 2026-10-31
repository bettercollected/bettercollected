import React, { useEffect } from 'react';

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { useDerivedAnswers } from '@app/lib/hooks/use-derived-answers';
import { statesFor, useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { resetSingleForm, setForm } from '@app/store/forms/slice';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';

const text = (value: string) => ({ type: 'text', text: value });
const question = (id: string, type: FieldTypes, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index: 0, type, title: id, ...extra });
const withRules = (id: string, type: FieldTypes, rules: unknown[], extra: Partial<StandardFormFieldDto> = {}) => question(id, type, { ...extra, properties: { ...extra.properties, rules: rules as any } });
const slide = (id: string, index: number, fields: StandardFormFieldDto[]) => ({ id, index, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;
const equals = (fieldId: string, value: string) => ({ conditions: [{ fieldId, fieldType: 'short_text', comparison: 'IS_EQUAL', value }] });
const filled = (fieldId: string) => ({ conditions: [{ fieldId, fieldType: 'short_text', comparison: 'IS_NOT_EMPTY' }] });

describe('what the rule states are decided from', () => {
    beforeEach(() => store.dispatch(resetSingleForm()));
    afterEach(cleanup);

    describe('a change of the answers that removes one', () => {
        const slides = [slide('p1', 0, [question('country', FieldTypes.SHORT_TEXT), withRules('postcode', FieldTypes.SHORT_TEXT, [{ id: 'r', when: filled('country'), then: { required: true } }])])];

        function Page() {
            const { responderState, setResponderState } = useResponderState();
            useEffect(() => {
                setResponderState({ ...responderState, currentSlide: 0 });
            }, []);
            const { addFieldTextAnswer, removeAnswer, formResponse } = useFormResponse();
            const states = useFieldRuleStates();
            return (
                <>
                    <button onClick={() => addFieldTextAnswer('country', 'NL')}>add</button>
                    <button onClick={() => removeAnswer('country')}>remove</button>
                    <output data-testid="required">{String(states.isRequired('postcode', false))}</output>
                    <output data-testid="answers">{Object.keys(formResponse.answers ?? {}).join(',')}</output>
                </>
            );
        }

        it('is seen at once (removeAnswer used to change the answers in place, so the states stayed)', async () => {
            store.dispatch(setForm({ title: 'Form', fields: slides }));
            render(
                <ReduxProvider store={store}>
                    <Provider>
                        <Page />
                    </Provider>
                </ReduxProvider>
            );
            expect(screen.getByTestId('required').textContent).toBe('false');
            await act(async () => fireEvent.click(screen.getByText('add')));
            expect(screen.getByTestId('required').textContent).toBe('true');
            expect(screen.getByTestId('answers').textContent).toBe('country');
            await act(async () => fireEvent.click(screen.getByText('remove')));
            expect(screen.getByTestId('answers').textContent).toBe('');
            expect(screen.getByTestId('required').textContent).toBe('false');
        });
    });

    describe('the answers as a submission carries them', () => {
        it('leave out a page the respondent did not go through', () => {
            const slides = [slide('p1', 0, [question('a', FieldTypes.SHORT_TEXT), withRules('b', FieldTypes.SHORT_TEXT, [{ id: 'r', when: equals('c', 'x'), then: { required: true } }])]), slide('p2', 1, [question('c', FieldTypes.SHORT_TEXT)])];
            const answers = { c: text('x') };
            expect(statesFor(slides, answers, {}, [], [0, 1]).isRequired('b', false)).toBe(true);
            // a jump skipped page 2: its answer is not submitted, so it decides nothing
            expect(statesFor(slides, answers, {}, [], [0]).isRequired('b', false)).toBe(false);
            // the visited path changes what is decided, with the same answers object
            expect(statesFor(slides, answers, {}, [], [0, 1]).isRequired('b', false)).toBe(true);
        });

        it('leave out a group that logic hides', () => {
            const group = question('g', FieldTypes.GROUP, {
                properties: {
                    repeat: { minItems: 1, maxItems: 3 },
                    fields: [question('item', FieldTypes.SHORT_TEXT)],
                    logic: { action: 'HIDE', operator: 'AND', conditions: [{ fieldId: 'a', fieldType: 'short_text', comparison: 'IS_EQUAL', value: 'hide' }] } as any
                }
            });
            const counted = { conditions: [{ fieldId: 'g', fieldType: 'group', comparison: 'GREATER_THAN', value: 0, groupMode: 'COUNT' }] };
            const slides = [slide('p1', 0, [question('a', FieldTypes.SHORT_TEXT), group, withRules('b', FieldTypes.SHORT_TEXT, [{ id: 'r', when: counted, then: { required: true } }])])];
            const items = { g: { type: 'group', items: [{ item: text('1') }, { item: text('2') }] } };
            expect(statesFor(slides, { ...items, a: text('show') }, {}, [], [0]).isRequired('b', false)).toBe(true);
            // hidden: the server drops the group, so it counts no items
            expect(statesFor(slides, { ...items, a: text('hide') }, {}, [], [0]).isRequired('b', false)).toBe(false);
        });
    });

    describe('the values written into the answers', () => {
        const slides = [slide('p1', 0, [question('a', FieldTypes.SHORT_TEXT), withRules('s', FieldTypes.SHORT_TEXT, [{ id: 'r', when: equals('c', 'x'), then: { setValue: { const: 'filled' } } }])]), slide('p2', 1, [question('c', FieldTypes.SHORT_TEXT)])];

        function Page({ visited }: { visited: { currentSlide: number; history: number[] } }) {
            const { responderState, setResponderState } = useResponderState();
            useEffect(() => {
                setResponderState({ ...responderState, ...visited });
            }, []);
            useDerivedAnswers(store.getState().form.fields);
            const { addFieldTextAnswer, formResponse } = useFormResponse();
            return (
                <>
                    <button onClick={() => addFieldTextAnswer('c', 'x')}>answer c</button>
                    <output data-testid="answers">{JSON.stringify(formResponse.answers ?? {})}</output>
                </>
            );
        }

        const show = (visited: { currentSlide: number; history: number[] }) => {
            store.dispatch(setForm({ title: 'Form', fields: slides }));
            render(
                <ReduxProvider store={store}>
                    <Provider>
                        <Page visited={visited} />
                    </Provider>
                </ReduxProvider>
            );
        };

        it('are worked out from the visited path: an answer on a page that was skipped sets nothing, and is not removed', async () => {
            show({ currentSlide: 0, history: [] });
            await act(async () => fireEvent.click(screen.getByText('answer c')));
            const answers = JSON.parse(screen.getByTestId('answers').textContent!);
            expect(answers.c).toEqual(text('x'));
            expect(answers.s).toBeUndefined();
        });

        it('and set the value once that page is on the path', async () => {
            show({ currentSlide: 1, history: [0] });
            await act(async () => fireEvent.click(screen.getByText('answer c')));
            const answers = JSON.parse(screen.getByTestId('answers').textContent!);
            expect(answers.s).toEqual(text('filled'));
            expect(answers.c).toEqual(text('x'));
        });
    });
});
