import React, { useEffect } from 'react';

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useDerivedAnswers } from '@app/lib/hooks/use-derived-answers';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { resetSingleForm, setForm } from '@app/store/forms/slice';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';

import DateField from './date-field';
import DropDownField from './drop-down-field';
import FieldRuleAnnouncer from './field-rule-announcer';
import InputField from './input-field';
import QuestionWrapper from './question-wrapper';
import TextAreaField from './text-area-field';

/**
 * What the reviews of the respondent runtime asked to pin: the keyboard block
 * of a locked question, a stale "required" going away (and the server's
 * staying), a locked text area never writing, the status region's focus rule
 * and cap, a locked date, and how an empty read-only question looks.
 */

// RenderImage drags in the whole builder field registry; irrelevant here.
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));

const isCountry = (value: string) => ({ conditions: [{ fieldId: 'country', fieldType: 'short_text', comparison: 'IS_EQUAL', value }] });
const ALWAYS = { expression: true };
const question = (id: string, type: FieldTypes, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index: 0, type, title: id[0].toUpperCase() + id.slice(1), ...extra });
const withRules = (id: string, type: FieldTypes, rules: unknown[], extra: Partial<StandardFormFieldDto> = {}) => question(id, type, { ...extra, properties: { ...extra.properties, rules: rules as any } });
const slide = (fields: StandardFormFieldDto[]) => ({ id: 'p1', index: 0, type: FieldTypes.SLIDE, properties: { fields } }) as StandardFormFieldDto;

const COUNTRY = question('country', FieldTypes.SHORT_TEXT);

/** The respondent is on the first page (rules are decided along the path they went). */
function useOnFirstPage() {
    const { responderState, setResponderState } = useResponderState();
    useEffect(() => {
        setResponderState({ ...responderState, currentSlide: 0 });
    }, []);
}

function mount(fields: StandardFormFieldDto[], page: React.ReactElement) {
    store.dispatch(setForm({ formId: 'f', title: 'Form', fields: [slide(fields)] }));
    return render(
        <ReduxProvider store={store}>
            <Provider>{page}</Provider>
        </ReduxProvider>
    );
}

const country = (value: string) => screen.getByText(value);
const input = (id: string) => document.getElementById(`input-field-${id}`) as HTMLInputElement;
const status = () => screen.getByTestId('field-rule-status').textContent ?? '';

describe('the keyboard block of a locked question', () => {
    beforeEach(() => store.dispatch(resetSingleForm()));
    afterEach(cleanup);

    const LOCKED = withRules('locked', FieldTypes.SHORT_TEXT, [{ id: 'rl', when: ALWAYS, then: { readOnly: true } }]);
    const OPEN = question('open', FieldTypes.SHORT_TEXT);

    function Probe({ field, onKey }: { field: StandardFormFieldDto; onKey: () => void }) {
        useOnFirstPage();
        return (
            <QuestionWrapper field={field}>
                <button onKeyDown={onKey}>press</button>
                <input aria-label="box" onKeyDown={onKey} />
            </QuestionWrapper>
        );
    }

    it("cancels Enter, a letter, Space and the arrows before they reach the question's buttons", async () => {
        const reached = vi.fn();
        mount([LOCKED], <Probe field={LOCKED} onKey={reached} />);
        const button = screen.getByText('press');
        await act(async () => {});
        expect(document.querySelector('[data-rule-locked]')).not.toBeNull();
        for (const key of ['Enter', 'a', ' ', 'ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight']) {
            expect(fireEvent.keyDown(button, { key }), key).toBe(false);
        }
        expect(reached).not.toHaveBeenCalled();
    });

    it('leaves Tab, a shortcut with a modifier and the text box alone', async () => {
        const reached = vi.fn();
        mount([LOCKED], <Probe field={LOCKED} onKey={reached} />);
        await act(async () => {});
        expect(fireEvent.keyDown(screen.getByText('press'), { key: 'Tab' })).toBe(true);
        expect(fireEvent.keyDown(screen.getByText('press'), { key: 'a', ctrlKey: true })).toBe(true);
        // a text box keeps its caret and selection (it is read-only natively)
        expect(fireEvent.keyDown(screen.getByLabelText('box'), { key: 'ArrowLeft' })).toBe(true);
        expect(reached).toHaveBeenCalledTimes(3);
    });

    it('does nothing for a question no rule locks', async () => {
        const reached = vi.fn();
        mount([OPEN], <Probe field={OPEN} onKey={reached} />);
        await act(async () => {});
        expect(fireEvent.keyDown(screen.getByText('press'), { key: 'Enter' })).toBe(true);
        expect(fireEvent.keyDown(screen.getByText('press'), { key: 'ArrowDown' })).toBe(true);
        expect(reached).toHaveBeenCalledTimes(2);
    });
});

describe('a "required" flagged earlier', () => {
    beforeEach(() => store.dispatch(resetSingleForm()));
    afterEach(cleanup);

    // required, unless the country is BE
    const NEEDED = withRules('needed', FieldTypes.SHORT_TEXT, [{ id: 'rn', when: isCountry('BE'), then: { required: false } }], { validations: { required: true } });

    function FlagPage({ code }: { code: number | string }) {
        useOnFirstPage();
        useDerivedAnswers(store.getState().form.fields);
        const { addFieldTextAnswer, setInvalidFields } = useFormResponse();
        return (
            <>
                <button onClick={() => addFieldTextAnswer('country', 'NL')}>NL</button>
                <button onClick={() => addFieldTextAnswer('country', 'BE')}>BE</button>
                <button onClick={() => setInvalidFields({ needed: [code] })}>flag</button>
                <InputField field={COUNTRY} />
                <InputField field={NEEDED} />
            </>
        );
    }

    it("goes away when a rule stops requiring the question (the page's own flag)", async () => {
        mount([COUNTRY, NEEDED], <FlagPage code={0} />);
        await act(async () => fireEvent.click(country('NL')));
        await act(async () => fireEvent.click(country('flag')));
        expect(screen.getByRole('alert')).toHaveTextContent('Please answer this question to continue.');
        await act(async () => fireEvent.click(country('BE')));
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        expect(input('needed').getAttribute('aria-invalid')).toBeNull();
        // and it is back when the rule lets go
        await act(async () => fireEvent.click(country('NL')));
        expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it("stays when it is the server's word, whatever the rules say now", async () => {
        mount([COUNTRY, NEEDED], <FlagPage code="REQUIRED" />);
        await act(async () => fireEvent.click(country('BE')));
        await act(async () => fireEvent.click(country('flag')));
        expect(screen.getByRole('alert')).toHaveTextContent('Please answer this question to continue.');
        expect(input('needed').getAttribute('aria-invalid')).toBe('true');
    });
});

describe('a text area a rule locks', () => {
    beforeEach(() => store.dispatch(resetSingleForm()));
    afterEach(cleanup);

    const MEMO = withRules('memo', FieldTypes.LONG_TEXT, [{ id: 'rm', when: isCountry('NL'), then: { setValue: { const: 'Filled in by the form' } } }]);
    let latest: Record<string, any> = {};
    let texts: Array<string | undefined> = [];

    function MemoPage() {
        useOnFirstPage();
        useDerivedAnswers(store.getState().form.fields);
        const { addFieldTextAnswer, formResponse } = useFormResponse();
        latest = formResponse.answers ?? {};
        texts.push(latest.memo?.text);
        return (
            <>
                <button onClick={() => addFieldTextAnswer('country', 'NL')}>NL</button>
                <TextAreaField field={MEMO} />
            </>
        );
    }

    it('never writes what is typed or left in it: not on blur, not after the debounce', async () => {
        texts = [];
        mount([COUNTRY, MEMO], <MemoPage />);
        await act(async () => fireEvent.click(country('NL')));
        const box = document.getElementById('input-field-memo') as HTMLTextAreaElement;
        expect(latest.memo?.text).toBe('Filled in by the form');
        await act(async () => {
            fireEvent.change(box, { target: { value: 'my own words' } });
            fireEvent.blur(box);
        });
        expect(latest.memo?.text).toBe('Filled in by the form');
        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 450));
        });
        expect(latest.memo?.text).toBe('Filled in by the form');
        expect(box.value).toBe('Filled in by the form');
        // not even for a moment (the page would only have set the value again)
        expect(texts.filter((text) => text !== undefined && text !== 'Filled in by the form')).toEqual([]);
    });
});

describe('the status region', () => {
    beforeEach(() => store.dispatch(resetSingleForm()));
    afterEach(cleanup);

    const needs = (id: string) => withRules(id, FieldTypes.SHORT_TEXT, [{ id: `r-${id}`, when: isCountry('NL'), then: { required: true } }]);
    const NOTE = withRules('note', FieldTypes.SHORT_TEXT, [{ id: 'rt', when: isCountry('NL'), then: { title: 'Opmerking', description: 'Only for the Netherlands' } }]);

    function AnnouncedPage({ fields }: { fields: StandardFormFieldDto[] }) {
        useOnFirstPage();
        useDerivedAnswers(store.getState().form.fields);
        const { addFieldTextAnswer } = useFormResponse();
        return (
            <>
                <button onClick={() => addFieldTextAnswer('country', 'NL')}>NL</button>
                <button onClick={() => addFieldTextAnswer('country', 'BE')}>BE</button>
                <FieldRuleAnnouncer fields={fields} />
                {fields.map((field) => (
                    <InputField key={field.id} field={field} />
                ))}
            </>
        );
    }

    it('names at most three changes in a message and counts the rest', async () => {
        const fields = [COUNTRY, ...['q1', 'q2', 'q3', 'q4', 'q5'].map(needs)];
        mount(fields, <AnnouncedPage fields={fields} />);
        await act(async () => fireEvent.click(country('NL')));
        const said = status();
        expect(said).toContain('“Q1” is now required.');
        expect(said).toContain('“Q2” is now required.');
        expect(said).toContain('“Q3” is now required.');
        expect(said).not.toContain('“Q4”');
        expect(said).not.toContain('“Q5”');
        expect(said).toContain('2 more changes on this page.');
        // one over the cap is counted as one more change
        const four = [COUNTRY, ...['q1', 'q2', 'q3', 'q4'].map(needs)];
        cleanup();
        store.dispatch(resetSingleForm());
        mount(four, <AnnouncedPage fields={four} />);
        await act(async () => fireEvent.click(country('NL')));
        expect(status()).toContain('1 more change on this page.');
    });

    it('says nothing about the state of the question the respondent is in', async () => {
        const fields = [COUNTRY, needs('q1'), needs('q2')];
        mount(fields, <AnnouncedPage fields={fields} />);
        act(() => input('q1').focus());
        await act(async () => fireEvent.click(country('NL')));
        // the control tells its own state; the other question is announced
        expect(status()).not.toContain('“Q1”');
        expect(status()).toContain('“Q2” is now required.');
    });

    it('does announce a new title or description of the question in focus, and is silent when the title goes back', async () => {
        const fields = [COUNTRY, NOTE];
        mount(fields, <AnnouncedPage fields={fields} />);
        act(() => input('note').focus());
        await act(async () => fireEvent.click(country('NL')));
        expect(status()).toContain('A question is now titled “Opmerking”.');
        expect(status()).toContain('The description of “Opmerking” changed.');
        await act(async () => fireEvent.click(country('BE')));
        // the title goes back to its own: not announced; the description that went is
        expect(status()).not.toContain('titled');
        expect(status()).toContain('The description of “Note” changed.');
    });
});

describe('a date a rule locks', () => {
    beforeEach(() => store.dispatch(resetSingleForm()));
    afterEach(cleanup);

    // 2026-03-10 is before the date every answer must be after
    const MUST_BE_LATE = { dateRules: [{ comparison: 'after', target: 'date', date: '2030-01-01' }] as any };
    const SET = withRules('when', FieldTypes.DATE, [{ id: 'rd', when: ALWAYS, then: { setValue: { const: '2026-03-10' } } }], { properties: MUST_BE_LATE });
    const FREE = question('when', FieldTypes.DATE, { properties: MUST_BE_LATE });
    const EMPTY_LOCKED = withRules('when', FieldTypes.DATE, [{ id: 'rd', when: ALWAYS, then: { readOnly: true } }]);

    function DatePage({ field, answer }: { field: StandardFormFieldDto; answer?: string }) {
        useOnFirstPage();
        useDerivedAnswers(store.getState().form.fields);
        const { addFieldDateAnswer } = useFormResponse();
        const [ready, setReady] = React.useState(false);
        useEffect(() => {
            if (answer) addFieldDateAnswer('when', answer);
            setReady(true);
        }, []);
        return ready ? <DateField field={field} /> : null;
    }

    const trigger = () => document.getElementById('date-picker-when') as HTMLButtonElement;

    it('is not held to its date rules, and its trigger is a read-only combobox the question blocks', async () => {
        mount([SET], <DatePage field={SET} />);
        await act(async () => {});
        expect(trigger().textContent).toContain('March 10th, 2026');
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        expect(trigger().getAttribute('role')).toBe('combobox');
        expect(trigger().getAttribute('aria-readonly')).toBe('true');
        // the click is cancelled before it opens the calendar
        await act(async () => {
            fireEvent.click(trigger());
        });
        expect(trigger().getAttribute('aria-expanded')).toBe('false');
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('is held to them when nothing locks it, as a plain button', async () => {
        mount([FREE], <DatePage field={FREE} answer="2026-03-10" />);
        await act(async () => {});
        expect(screen.getByRole('alert')).toHaveTextContent('Must be after');
        expect(trigger().getAttribute('role')).toBeNull();
        expect(trigger().getAttribute('aria-readonly')).toBeNull();
    });

    it('shows a dash, not "Pick a date", while locked with no value', async () => {
        mount([EMPTY_LOCKED], <DatePage field={EMPTY_LOCKED} />);
        await act(async () => {});
        expect(trigger().textContent).toBe('–');
        cleanup();
        store.dispatch(resetSingleForm());
        mount([FREE], <DatePage field={FREE} />);
        await act(async () => {});
        expect(trigger().textContent).toContain('Pick a date');
    });
});

describe('an empty read-only question', () => {
    beforeEach(() => store.dispatch(resetSingleForm()));
    afterEach(cleanup);

    const LOCKED_TEXT = withRules('lock', FieldTypes.SHORT_TEXT, [{ id: 'rl', when: ALWAYS, then: { readOnly: true } }]);
    const LOCKED_AREA = withRules('area', FieldTypes.LONG_TEXT, [{ id: 'ra', when: ALWAYS, then: { readOnly: true } }]);
    const LOCKED_NUMBER = withRules('count', FieldTypes.NUMBER, [{ id: 'rc', when: ALWAYS, then: { readOnly: true } }]);
    const LOCKED_CHOICE = withRules('pick', FieldTypes.DROP_DOWN, [{ id: 'rp', when: ALWAYS, then: { setValue: { const: 'nl' } } }], {
        properties: {
            choices: [
                { id: 'nl', value: 'Netherlands' },
                { id: 'be', value: 'Belgium' }
            ],
            rules: [{ id: 'rp', when: ALWAYS, then: { setValue: { const: 'nl' } } }] as any
        }
    });
    const EMPTY_LOCKED_CHOICE = withRules('pick', FieldTypes.DROP_DOWN, [{ id: 'rp', when: ALWAYS, then: { readOnly: true } }], {
        properties: {
            choices: [
                { id: 'nl', value: 'Netherlands' },
                { id: 'be', value: 'Belgium' }
            ],
            rules: [{ id: 'rp', when: ALWAYS, then: { readOnly: true } }] as any
        }
    });

    function Page({ children }: { children: React.ReactNode }) {
        useOnFirstPage();
        useDerivedAnswers(store.getState().form.fields);
        return <>{children}</>;
    }

    it('shows a dash where an open question shows its prompt', async () => {
        mount(
            [LOCKED_TEXT, LOCKED_AREA, LOCKED_NUMBER, question('free', FieldTypes.SHORT_TEXT)],
            <Page>
                {[LOCKED_TEXT, LOCKED_NUMBER, question('free', FieldTypes.SHORT_TEXT)].map((field) => (
                    <InputField key={field.id} field={field} />
                ))}
                <TextAreaField field={LOCKED_AREA} />
            </Page>
        );
        await act(async () => {});
        expect(input('lock').placeholder).toBe('–');
        expect(input('area').placeholder).toBe('–');
        expect(input('count').placeholder).toBe('–');
        expect(input('free').placeholder).toBe('Answer');
    });

    it('gives a locked dropdown read-only semantics, and an open one none', async () => {
        mount(
            [EMPTY_LOCKED_CHOICE],
            <Page>
                <DropDownField field={EMPTY_LOCKED_CHOICE} slideIndex={0} />
            </Page>
        );
        await act(async () => {});
        const locked = screen.getByRole('combobox');
        expect(locked.getAttribute('aria-readonly')).toBe('true');
        expect(locked.textContent).toBe('–');
        await act(async () => {
            fireEvent.click(locked);
        });
        expect(locked.getAttribute('aria-expanded')).toBe('false');
        cleanup();
        store.dispatch(resetSingleForm());
        const open = question('pick', FieldTypes.DROP_DOWN, { properties: { choices: [{ id: 'nl', value: 'Netherlands' }] } });
        mount(
            [open],
            <Page>
                <DropDownField field={open} slideIndex={0} />
            </Page>
        );
        await act(async () => {});
        expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
        expect(screen.getByRole('button').textContent).toContain('Select an option');
    });

    it('shows the value a rule set in a locked dropdown', async () => {
        mount(
            [LOCKED_CHOICE],
            <Page>
                <DropDownField field={LOCKED_CHOICE} slideIndex={0} />
            </Page>
        );
        await act(async () => {});
        expect(screen.getByRole('combobox').textContent).toBe('Netherlands');
    });
});
