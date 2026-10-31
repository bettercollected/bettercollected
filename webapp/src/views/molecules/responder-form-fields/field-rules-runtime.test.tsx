import React, { useEffect } from 'react';

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { resolveFieldRules } from '@app/lib/field-rules';
import { useDerivedAnswers } from '@app/lib/hooks/use-derived-answers';
import { useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { resetSingleForm, setForm } from '@app/store/forms/slice';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { validateSlide } from '@app/utils/vvalidation-utils';

import DateField from './date-field';
import DropDownField from './drop-down-field';
import FieldRuleAnnouncer from './field-rule-announcer';
import InputField from './input-field';
import QuestionWrapper from './question-wrapper';
import TextAreaField from './text-area-field';
import YesNoField from './yes-no-field';

// RenderImage drags in the whole builder field registry; irrelevant here.
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));

const isCountry = (value: string) => ({ conditions: [{ fieldId: 'country', fieldType: 'short_text', comparison: 'IS_EQUAL', value }] });

const COUNTRY: StandardFormFieldDto = { id: 'country', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Country' };
const POSTCODE: StandardFormFieldDto = {
    id: 'postcode',
    index: 1,
    type: FieldTypes.SHORT_TEXT,
    title: 'Postcode',
    properties: { rules: [{ id: 'r1', when: isCountry('NL'), then: { required: true, description: 'Required for Dutch addresses' } }] }
};
const QTY: StandardFormFieldDto = { id: 'qty', index: 2, type: FieldTypes.NUMBER, title: 'Quantity' };
const TOTAL: StandardFormFieldDto = {
    id: 'total',
    index: 3,
    type: FieldTypes.NUMBER,
    title: 'Total',
    properties: { rules: [{ id: 'r2', when: { expression: { '>': [{ var: 'qty' }, 0] } }, then: { setValue: { expression: { '*': [{ var: 'qty' }, 5] } } } }] }
};
const NOTE: StandardFormFieldDto = {
    id: 'note',
    index: 4,
    type: FieldTypes.SHORT_TEXT,
    title: 'Note',
    properties: { rules: [{ id: 'r3', when: isCountry('NL'), then: { title: 'Opmerking' } }] }
};
const slide = (fields: StandardFormFieldDto[]) => ({ id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;
const WITH_RULES = [slide([COUNTRY, POSTCODE, QTY, TOTAL, NOTE])];
const WITHOUT_RULES = [slide([COUNTRY, { ...POSTCODE, properties: {} }, QTY])];

/** The respondent is on the first page (rules are decided along the path they went). */
function useOnFirstPage() {
    const { responderState, setResponderState } = useResponderState();
    useEffect(() => {
        setResponderState({ ...responderState, currentSlide: 0 });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
}

/** A page as FormSlide builds it: the derived-answers hook, the status region and the fields. */
function Page({ fields }: { fields: StandardFormFieldDto[] }) {
    useOnFirstPage();
    useDerivedAnswers(store.getState().form.fields);
    const { addFieldTextAnswer, addFieldNumberAnswer } = useFormResponse();
    const states = useFieldRuleStates();
    return (
        <>
            <button onClick={() => addFieldTextAnswer('country', 'NL')}>NL</button>
            <button onClick={() => addFieldTextAnswer('country', 'BE')}>BE</button>
            <button onClick={() => addFieldNumberAnswer('qty', 3)}>three</button>
            <output data-testid="postcode-required">{String(states.isRequired('postcode', false))}</output>
            <FieldRuleAnnouncer fields={fields} />
            {fields.map((field) => (
                <InputField key={field.id} field={field} />
            ))}
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

const input = (id: string) => document.getElementById(`input-field-${id}`) as HTMLInputElement;

describe('field rules on the respondent page', () => {
    beforeEach(() => {
        store.dispatch(resetSingleForm());
    });
    afterEach(cleanup);

    it('marks a question required (visibly and to assistive tech) when its rule holds, and says so once', async () => {
        renderPage(WITH_RULES);
        expect(input('postcode').getAttribute('aria-required')).toBeNull();
        expect(screen.getAllByText('Optional').length).toBeGreaterThan(0);
        expect(screen.getByTestId('field-rule-status').textContent).toBe('');

        await act(async () => fireEvent.click(screen.getByText('NL')));
        expect(input('postcode').getAttribute('aria-required')).toBe('true');
        expect(document.getElementById('q-required-postcode')?.textContent).toContain('required');
        expect(screen.getByText('Required for Dutch addresses')).toBeInTheDocument();
        expect(input('postcode').getAttribute('aria-describedby')).toContain('q-desc-postcode');
        const status = screen.getByTestId('field-rule-status');
        expect(status.getAttribute('aria-live')).toBe('polite');
        expect(status.textContent).toContain('“Postcode” is now required.');
        // the label change is announced too, in the same message
        expect(status.textContent).toContain('A question is now titled “Opmerking”.');

        // back to optional: said, and the marker goes
        await act(async () => fireEvent.click(screen.getByText('BE')));
        expect(input('postcode').getAttribute('aria-required')).toBeNull();
        expect(status.textContent).toContain('“Postcode” is now optional.');
    });

    it('changes the label a rule names while it holds', async () => {
        renderPage(WITH_RULES);
        expect(screen.queryByText('Opmerking')).not.toBeInTheDocument();
        await act(async () => fireEvent.click(screen.getByText('NL')));
        expect(screen.getByText('Opmerking')).toBeInTheDocument();
        expect(document.getElementById('input-field-note')?.getAttribute('aria-labelledby')).toBe('q-title-note');
    });

    it('fills in a set value, shows it read-only (not disabled) and feeds it back', async () => {
        renderPage(WITH_RULES);
        expect(input('total').readOnly).toBe(false);
        await act(async () => fireEvent.click(screen.getByText('three')));
        expect(input('total').value).toBe('15');
        expect(input('total').readOnly).toBe(true);
        expect(input('total').disabled).toBe(false);
        expect(input('total').getAttribute('aria-readonly')).toBe('true');
        expect(input('total').tabIndex).toBeGreaterThanOrEqual(0);
        // named by its question, described by the read-only note, no "Optional" label
        expect(input('total').getAttribute('aria-describedby')).toContain('q-locked-total');
        expect(document.getElementById('q-locked-total')?.textContent).toBe('Read only');
        expect(document.querySelector('[data-testid="field-rule-status"]')?.textContent).toContain('“Total” was filled in for you and is read only.');
    });

    it('renders a page without rules with no status region and no read-only markers', async () => {
        renderPage(WITHOUT_RULES);
        await act(async () => fireEvent.click(screen.getByText('three')));
        expect(screen.queryByTestId('field-rule-status')).not.toBeInTheDocument();
        expect(document.querySelector('[data-rule-locked], [data-rule-readonly], [aria-readonly]')).toBeNull();
        expect(screen.getByTestId('postcode-required').textContent).toBe('false');
    });

    it('validates Required with the rules applied', () => {
        const nl = { country: { type: 'text', text: 'NL' } };
        const be = { country: { type: 'text', text: 'BE' } };
        expect(validateSlide(WITH_RULES[0], nl, resolveFieldRules(WITH_RULES, nl).states)).toEqual({ postcode: [0] });
        expect(validateSlide(WITH_RULES[0], be, resolveFieldRules(WITH_RULES, be).states)).toEqual({});
        // without states the static flag decides, as before rules existed
        expect(validateSlide(WITH_RULES[0], nl)).toEqual({});
    });

    it('keeps a locked yes or no from being changed, though it stays focusable', async () => {
        const OK: StandardFormFieldDto = {
            id: 'ok',
            index: 0,
            type: FieldTypes.YES_NO,
            title: 'Agreed',
            properties: { rules: [{ id: 'r9', when: isCountry('NL'), then: { setValue: { const: 'Yes' } } }] }
        };
        const slides = [slide([COUNTRY, OK])];
        store.dispatch(setForm({ title: 'Form', fields: slides }));
        function YesNoPage() {
            useOnFirstPage();
            useDerivedAnswers(store.getState().form.fields);
            const { addFieldTextAnswer, formResponse } = useFormResponse();
            return (
                <>
                    <button onClick={() => addFieldTextAnswer('country', 'NL')}>NL</button>
                    <output data-testid="answer">{JSON.stringify(formResponse.answers?.ok ?? null)}</output>
                    <YesNoField field={OK} />
                </>
            );
        }
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <YesNoPage />
                </Provider>
            </ReduxProvider>
        );
        await act(async () => fireEvent.click(screen.getByText('NL')));
        expect(screen.getByTestId('answer').textContent).toBe('{"type":"boolean","boolean":true}');
        const group = screen.getByRole('radiogroup');
        expect(group.getAttribute('aria-readonly')).toBe('true');
        const no = screen.getByRole('radio', { name: 'No' });
        expect((no as HTMLButtonElement).disabled).toBe(false);
        // the question's own buttons do nothing: the click is cancelled before it reaches them,
        // and an arrow key moves focus from option to option without choosing
        let clicked = true;
        let keyed = true;
        no.focus();
        await act(async () => {
            clicked = fireEvent.click(no);
            keyed = fireEvent.keyDown(no, { key: 'ArrowDown' });
        });
        expect(clicked).toBe(false);
        expect(keyed).toBe(false);
        expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'Yes' }));
        expect(screen.getByTestId('answer').textContent).toBe('{"type":"boolean","boolean":true}');
        await act(async () => fireEvent.keyDown(document.activeElement!, { key: 'ArrowUp' }));
        expect(document.activeElement).toBe(no);
        expect(screen.getByTestId('answer').textContent).toBe('{"type":"boolean","boolean":true}');
    });

    it('shows a set text in a text area, read-only, and lets go of it when the rule stops', async () => {
        const MEMO: StandardFormFieldDto = {
            id: 'memo',
            index: 0,
            type: FieldTypes.LONG_TEXT,
            title: 'Memo',
            properties: { rules: [{ id: 'r8', when: isCountry('NL'), then: { setValue: { const: 'Filled in by the form' } } }] }
        };
        const slides = [slide([COUNTRY, MEMO])];
        store.dispatch(setForm({ title: 'Form', fields: slides }));
        function MemoPage() {
            useOnFirstPage();
            useDerivedAnswers(store.getState().form.fields);
            const { addFieldTextAnswer } = useFormResponse();
            return (
                <>
                    <button onClick={() => addFieldTextAnswer('country', 'NL')}>NL</button>
                    <button onClick={() => addFieldTextAnswer('country', 'BE')}>BE</button>
                    <TextAreaField field={MEMO} />
                </>
            );
        }
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <MemoPage />
                </Provider>
            </ReduxProvider>
        );
        const box = () => document.getElementById('input-field-memo') as HTMLTextAreaElement;
        expect(box().value).toBe('');
        await act(async () => fireEvent.click(screen.getByText('NL')));
        expect(box().value).toBe('Filled in by the form');
        expect(box().readOnly).toBe(true);
        expect(box().getAttribute('aria-readonly')).toBe('true');
        await act(async () => fireEvent.click(screen.getByText('BE')));
        expect(box().readOnly).toBe(false);
        expect(box().getAttribute('aria-readonly')).toBeNull();
    });
});
