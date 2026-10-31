// Respondent text resolves through the app's i18n instance.
import '@app/shared/hocs/i18n-provider';
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import axe from 'axe-core';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { setForm } from '@app/store/forms/slice';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { store } from '@app/store/store';
import { checkAnswerRules } from '@app/utils/answer-rules';

import CurrencyField from './currency-field';
import DateRangeField from './date-range-field';
import DayField from './day-field';
import TagsField from './tags-field';
import TimeField from './time-field';

// A field rule that locks the question (read-only, or the form sets its value).
const served = vi.hoisted(() => ({ locked: false }));
vi.mock('@app/lib/hooks/use-field-rule-states', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@app/lib/hooks/use-field-rule-states')>();
    // the states are an object with methods: only the answer to "is it locked" is replaced
    return { ...actual, useFieldRuleStates: () => new Proxy(actual.useFieldRuleStates(), { get: (target, key) => (key === 'isLocked' ? () => served.locked : Reflect.get(target, key)) }) };
});

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const time: StandardFormFieldDto = { id: 'arrival', index: 0, type: FieldTypes.TIME, title: 'When do you arrive?', description: 'Doors open early', properties: { minTime: '08:00', maxTime: '17:30' }, validations: { required: true } };
const day: StandardFormFieldDto = { id: 'born', index: 1, type: FieldTypes.DAY, title: 'When were you born?', properties: {} };
const money: StandardFormFieldDto = { id: 'budget', index: 2, type: FieldTypes.CURRENCY, title: 'What is your budget?', properties: { currencies: ['EUR', 'GBP'] } };
const oneCurrency: StandardFormFieldDto = { id: 'fee', index: 3, type: FieldTypes.CURRENCY, title: 'What is the fee?', properties: {} };
const stay: StandardFormFieldDto = { id: 'stay', index: 4, type: FieldTypes.DATE_RANGE, title: 'When do you stay?', properties: {} };
const topics: StandardFormFieldDto = { id: 'topics', index: 5, type: FieldTypes.TAGS, title: 'What interests you?', validations: { maxChoices: 3, maxLength: 12 } };
const plainTags: StandardFormFieldDto = { id: 'plain', index: 6, type: FieldTypes.TAGS, title: 'Any other topics?', validations: { minChoices: 2 } };

let latest: Record<string, any> = {};

function Spy() {
    const { formResponse } = useFormResponse();
    latest = formResponse.answers ?? {};
    return null;
}

const show = (field: StandardFormFieldDto, Component: React.ComponentType<{ field: StandardFormFieldDto }>, answers: Record<string, any> = {}) => {
    store.dispatch(setForm({ formId: 'f', title: 'Typed', fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [time, day, money, oneCurrency, stay, topics, plainTags] } }] }));
    const Harness = () => {
        const { setFormResponse, formResponse } = useFormResponse();
        const [ready, setReady] = React.useState(false);
        React.useEffect(() => {
            setFormResponse({ ...formResponse, answers });
            setReady(true);
             
        }, []);
        return ready ? <Component field={field} /> : null;
    };
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Harness />
                <Spy />
            </Provider>
        </ReduxProvider>
    );
};

afterEach(() => {
    latest = {};
    served.locked = false;
});

describe('TimeField', () => {
    it('is a time box named by the question and described by its window', async () => {
        show(time, TimeField);
        const input = await screen.findByLabelText('When do you arrive?');
        expect(input).toHaveAttribute('type', 'time');
        expect(input).toHaveAttribute('min', '08:00');
        expect(input).toHaveAttribute('max', '17:30');
        expect(input).toBeRequired();
        expect(input).toHaveAccessibleDescription(/Doors open early.*From 08:00 to 17:30/);
    });

    it('stores HH:MM and drops the answer when the box is emptied', async () => {
        show(time, TimeField);
        const input = await screen.findByLabelText('When do you arrive?');
        fireEvent.change(input, { target: { value: '09:30' } });
        expect(latest.arrival).toEqual({ type: 'time', time: '09:30' });
        fireEvent.change(input, { target: { value: '' } });
        expect(latest.arrival).toBeUndefined();
    });

    it('shows a locked time as it is and cannot be changed', async () => {
        served.locked = true;
        show(time, TimeField, { arrival: { type: 'time', time: '09:30' } });
        const input = await screen.findByLabelText('When do you arrive?');
        expect(input).toHaveAttribute('readonly');
        fireEvent.change(input, { target: { value: '10:45' } });
        expect(latest.arrival.time).toBe('09:30');
    });

    it('shows a stored time', async () => {
        show(time, TimeField, { arrival: { type: 'time', time: '16:45' } });
        expect(await screen.findByLabelText('When do you arrive?')).toHaveValue('16:45');
    });

    it('passes axe', async () => {
        const { container } = show(time, TimeField);
        await screen.findByLabelText('When do you arrive?');
        const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => v.id)).toEqual([]);
    });
});

describe('DayField', () => {
    it('is a group of three labelled boxes named by the question, in the order day, month, year', async () => {
        show(day, DayField);
        const group = await screen.findByRole('group', { name: 'When were you born?' });
        const boxes = within(group).getAllByRole('textbox');
        expect(boxes.map((box) => box.getAttribute('id'))).toEqual(['day-day-born', 'day-month-born', 'day-year-born']);
        expect(within(group).getByLabelText('Day')).toHaveAttribute('inputmode', 'numeric');
        expect(within(group).getByLabelText('Month')).toHaveAttribute('maxlength', '2');
        expect(within(group).getByLabelText('Year')).toHaveAttribute('maxlength', '4');
    });

    it('stores the calendar day as YYYY-MM-DD, keeping only digits', async () => {
        show(day, DayField);
        fireEvent.change(await screen.findByLabelText('Day'), { target: { value: '5a' } });
        fireEvent.change(screen.getByLabelText('Month'), { target: { value: '11' } });
        fireEvent.change(screen.getByLabelText('Year'), { target: { value: '1990' } });
        expect(latest.born).toEqual({ type: 'date', date: '1990-11-05' });
        expect(screen.getByLabelText('Day')).toHaveValue('5');
    });

    it('keeps an incomplete or impossible date as typed, so it is flagged and never lost', async () => {
        show(day, DayField);
        fireEvent.change(await screen.findByLabelText('Day'), { target: { value: '31' } });
        fireEvent.change(screen.getByLabelText('Month'), { target: { value: '02' } });
        expect(latest.born.date).toBe('-02-31');
        expect(checkAnswerRules(day, latest.born)).toEqual(['FORMAT']);
        fireEvent.change(screen.getByLabelText('Year'), { target: { value: '2026' } });
        expect(latest.born.date).toBe('2026-02-31');
        expect(checkAnswerRules(day, latest.born)).toEqual(['FORMAT']);
        fireEvent.change(screen.getByLabelText('Day'), { target: { value: '28' } });
        expect(checkAnswerRules(day, latest.born)).toEqual([]);
    });

    it('never pads a short year into one that was not typed', async () => {
        show(day, DayField);
        fireEvent.change(await screen.findByLabelText('Day'), { target: { value: '5' } });
        fireEvent.change(screen.getByLabelText('Month'), { target: { value: '11' } });
        for (const year of ['9', '90', '199']) {
            fireEvent.change(screen.getByLabelText('Year'), { target: { value: year } });
            expect(latest.born.date).toBe(`${year}-11-05`);
            expect(checkAnswerRules(day, latest.born)).toEqual(['FORMAT']);
            expect(screen.getByLabelText('Year')).toHaveValue(year);
        }
        fireEvent.change(screen.getByLabelText('Year'), { target: { value: '1990' } });
        expect(latest.born.date).toBe('1990-11-05');
        expect(checkAnswerRules(day, latest.born)).toEqual([]);
    });

    it('shows the boxes of a locked day as they are and cannot be typed over', async () => {
        served.locked = true;
        show(day, DayField, { born: { type: 'date', date: '1990-11-05' } });
        const dayBox = await screen.findByLabelText('Day');
        expect(dayBox).toHaveAttribute('readonly');
        fireEvent.change(dayBox, { target: { value: '9' } });
        expect(latest.born.date).toBe('1990-11-05');
    });

    it('drops the answer when all three boxes are emptied', async () => {
        show(day, DayField, { born: { type: 'date', date: '1990-11-05' } });
        expect(await screen.findByLabelText('Day')).toHaveValue('05');
        fireEvent.change(screen.getByLabelText('Day'), { target: { value: '' } });
        fireEvent.change(screen.getByLabelText('Month'), { target: { value: '' } });
        fireEvent.change(screen.getByLabelText('Year'), { target: { value: '' } });
        expect(latest.born).toBeUndefined();
    });

    it('explains a day that breaks a date rule', async () => {
        const rule: StandardFormFieldDto = { ...day, properties: { dateRules: [{ comparison: 'before', target: 'date', date: '2000-01-01' }] } };
        show(rule, DayField, { born: { type: 'date', date: '2010-05-01' } });
        expect(await screen.findByRole('alert')).toHaveTextContent('Must be before 1 Jan 2000.');
    });

    it('passes axe', async () => {
        const { container } = show(day, DayField);
        await screen.findByRole('group', { name: 'When were you born?' });
        const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => v.id)).toEqual([]);
    });
});

describe('CurrencyField', () => {
    it('offers the currencies as a choice and takes the amount in a decimal box', async () => {
        show(money, CurrencyField);
        const amount = await screen.findByLabelText('What is your budget?');
        expect(amount).toHaveAttribute('inputmode', 'decimal');
        expect(amount).toHaveAccessibleDescription('Choose the currency, then enter the amount');
        const code = screen.getByRole('combobox', { name: 'Currency' });
        expect(within(code).getAllByRole('option').map((o) => o.textContent)).toEqual(['EUR', 'GBP']);
    });

    it('stores the amount as a plain decimal with the chosen code, reading a comma as the decimal point', async () => {
        show(money, CurrencyField);
        const amount = await screen.findByLabelText('What is your budget?');
        fireEvent.change(amount, { target: { value: '12,5' } });
        expect(latest.budget).toEqual({ type: 'currency', currency: { code: 'EUR', amount: '12.5' } });
        fireEvent.change(screen.getByRole('combobox', { name: 'Currency' }), { target: { value: 'GBP' } });
        expect(latest.budget.currency).toEqual({ code: 'GBP', amount: '12.5' });
        expect(amount).toHaveValue('12,5');
    });

    it('stores what is typed, so a mistake is flagged rather than lost', async () => {
        show(money, CurrencyField);
        fireEvent.change(await screen.findByLabelText('What is your budget?'), { target: { value: '1.250,00' } });
        expect(latest.budget.currency.amount).toBe('1.250.00');
        expect(checkAnswerRules(money, latest.budget)).toEqual(['FORMAT']);
    });

    it('writes a minus zero as zero, and flags a negative amount while the question has no negative lowest amount', async () => {
        show(money, CurrencyField);
        const amount = await screen.findByLabelText('What is your budget?');
        fireEvent.change(amount, { target: { value: '-0' } });
        expect(latest.budget.currency.amount).toBe('0');
        fireEvent.change(amount, { target: { value: '-0,00' } });
        expect(latest.budget.currency.amount).toBe('0.00');
        fireEvent.change(amount, { target: { value: '-5' } });
        expect(latest.budget.currency.amount).toBe('-5');
        expect(checkAnswerRules(money, latest.budget)).toEqual(['TOO_SMALL']);
        expect(checkAnswerRules({ ...money, validations: { minValue: -10 } }, latest.budget)).toEqual([]);
    });

    it('shows a locked amount as it is and cannot be typed over', async () => {
        served.locked = true;
        show(money, CurrencyField, { budget: { type: 'currency', currency: { code: 'EUR', amount: '12.50' } } });
        const amount = await screen.findByLabelText('What is your budget?');
        expect(amount).toHaveAttribute('readonly');
        fireEvent.change(amount, { target: { value: '99' } });
        expect(latest.budget.currency.amount).toBe('12.50');
    });

    it('drops the answer when the amount is emptied', async () => {
        show(money, CurrencyField, { budget: { type: 'currency', currency: { code: 'GBP', amount: '3' } } });
        const amount = await screen.findByLabelText('What is your budget?');
        expect(amount).toHaveValue('3');
        expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveValue('GBP');
        fireEvent.change(amount, { target: { value: '' } });
        expect(latest.budget).toBeUndefined();
    });

    it('with one currency shows its code beside the box and says which it is', async () => {
        show(oneCurrency, CurrencyField);
        const amount = await screen.findByLabelText('What is the fee?');
        expect(screen.queryByRole('combobox')).toBeNull();
        expect(amount).toHaveAccessibleDescription('Amount in EUR');
        act(() => void fireEvent.change(amount, { target: { value: '99.95' } }));
        expect(latest.fee.currency).toEqual({ code: 'EUR', amount: '99.95' });
    });

    it('passes axe', async () => {
        const { container } = show(money, CurrencyField);
        await screen.findByLabelText('What is your budget?');
        const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => v.id)).toEqual([]);
    });
});

describe('DateRangeField', () => {
    it('is a group named by the question with a Start and an End picker', async () => {
        show(stay, DateRangeField);
        const group = await screen.findByRole('group', { name: 'When do you stay?' });
        expect(within(group).getByRole('button', { name: 'Start' })).toHaveTextContent('Pick a date');
        expect(within(group).getByRole('button', { name: 'End' })).toHaveTextContent('Pick a date');
        // both are visible labels, tied to their picker
        expect(screen.getByText('Start')).toBeVisible();
        expect(screen.getByText('End').getAttribute('for')).toBe('date-range-end-stay');
    });

    it('shows a stored range as two long dates', async () => {
        show(stay, DateRangeField, { stay: { type: 'date_range', date_range: { start: '2026-11-03', end: '2026-11-07' } } });
        expect(await screen.findByRole('button', { name: 'Start' })).toHaveTextContent('November 3rd, 2026');
        expect(screen.getByRole('button', { name: 'End' })).toHaveTextContent('November 7th, 2026');
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it('stores the start and the end as chosen in the calendar', async () => {
        show(stay, DateRangeField, { stay: { type: 'date_range', date_range: { start: '2026-11-03', end: '' } } });
        fireEvent.click(await screen.findByRole('button', { name: 'End' }));
        fireEvent.click(await screen.findByRole('button', { name: /November 7th, 2026/ }));
        expect(latest.stay).toEqual({ type: 'date_range', date_range: { start: '2026-11-03', end: '2026-11-07' } });
    });

    it('keeps the end from being picked before the start', async () => {
        show(stay, DateRangeField, { stay: { type: 'date_range', date_range: { start: '2026-11-10', end: '' } } });
        fireEvent.click(await screen.findByRole('button', { name: 'End' }));
        expect(await screen.findByRole('button', { name: /November 9th, 2026/ })).toBeDisabled();
        expect(screen.getByRole('button', { name: /November 10th, 2026/ })).toBeEnabled();
    });

    it('starts a range with only one end, to be finished before it can be sent', async () => {
        show(stay, DateRangeField);
        fireEvent.click(await screen.findByRole('button', { name: 'Start' }));
        const days = (await within(await screen.findByRole('dialog')).findAllByRole('button')).filter((day) => /, \d{4}$/.test(day.getAttribute('aria-label') ?? ''));
        fireEvent.click(days[0]);
        expect(latest.stay.date_range.start).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(latest.stay.date_range.end).toBe('');
        expect(checkAnswerRules(stay, latest.stay)).toEqual(['REQUIRED']);
    });

    it('says right away that the end is before the start', async () => {
        show(stay, DateRangeField, { stay: { type: 'date_range', date_range: { start: '2026-11-07', end: '2026-11-03' } } });
        expect(await screen.findByRole('alert')).toHaveTextContent('The end is before the start. Choose an end on or after the start.');
        expect(screen.getByRole('button', { name: 'End' })).toHaveAccessibleDescription(/before the start/);
    });

    it('applies the question’s date rules to each end', async () => {
        const rule: StandardFormFieldDto = { ...stay, properties: { dateRules: [{ comparison: 'before', target: 'date', date: '2026-12-03' }] } };
        show(rule, DateRangeField, { stay: { type: 'date_range', date_range: { start: '2026-12-02', end: '2026-12-03' } } });
        expect(await screen.findByRole('alert')).toHaveTextContent('End: Must be before 3 Dec 2026.');
    });

    it('writes the labels and messages in Dutch for a Dutch form', async () => {
        window.history.pushState({}, '', '/?lang=nl');
        try {
            show(stay, DateRangeField, { stay: { type: 'date_range', date_range: { start: '2026-11-07', end: '2026-11-03' } } });
            expect(await screen.findByRole('button', { name: 'Begin' })).toHaveTextContent('7 november 2026');
            expect(screen.getByRole('button', { name: 'Einde' })).toHaveTextContent('3 november 2026');
            expect(screen.getByRole('alert')).toHaveTextContent('Het einde ligt v\u00f3\u00f3r het begin.');
        } finally {
            window.history.pushState({}, '', '/');
        }
    });

    it('passes axe', async () => {
        const { container } = show(stay, DateRangeField, { stay: { type: 'date_range', date_range: { start: '2026-11-07', end: '2026-11-03' } } });
        await screen.findByRole('group', { name: 'When do you stay?' });
        const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => v.id)).toEqual([]);
    });
});

describe('TagsField', () => {
    const type = (input: HTMLElement, text: string) => fireEvent.change(input, { target: { value: text } });
    const press = (input: HTMLElement, key: string) => fireEvent.keyDown(input, { key });

    it('is a text box with a visible label, named by the question and described by its hint and count', async () => {
        show(topics, TagsField);
        const input = await screen.findByLabelText(/Add a tag/);
        expect(screen.getByText('Add a tag')).toBeVisible();
        expect(input).toHaveAccessibleName('What interests you? Add a tag');
        expect(input).toHaveAccessibleDescription(/Press Enter, a comma or a semicolon after each tag\..*0 of 3 tags/);
        expect(input).toHaveAttribute('id', 'tags-input-topics');
    });

    it('adds the typed tag on Enter, a comma or a semicolon, trimmed', async () => {
        show(topics, TagsField);
        const input = await screen.findByLabelText(/Add a tag/);
        type(input, '  vegan ');
        press(input, 'Enter');
        expect(latest.topics).toEqual({ type: 'tags', tags: ['vegan'] });
        expect(input).toHaveValue('');
        type(input, 'gluten free');
        press(input, ',');
        type(input, 'halal');
        press(input, ';');
        expect(latest.topics.tags).toEqual(['vegan', 'gluten free', 'halal']);
        expect(screen.getByRole('list', { name: 'Tags you added' }).querySelectorAll('li')).toHaveLength(3);
    });

    it('splits what is typed or pasted with commas and semicolons', async () => {
        show(topics, TagsField);
        const input = await screen.findByLabelText(/Add a tag/);
        type(input, 'a, b; c');
        expect(latest.topics.tags).toEqual(['a', 'b', 'c']);
        expect(input).toHaveValue('');
        // a fourth is refused (three is the most) and stays in the box
        type(input, 'd, e');
        expect(latest.topics.tags).toEqual(['a', 'b', 'c']);
        expect(input).toHaveValue('d, e');
    });

    it('ignores an empty tag and adds nothing', async () => {
        show(topics, TagsField);
        const input = await screen.findByLabelText(/Add a tag/);
        type(input, '   ');
        press(input, 'Enter');
        press(input, ',');
        expect(latest.topics).toBeUndefined();
    });

    it('adds the text left in the box when it loses focus', async () => {
        show(topics, TagsField);
        const input = await screen.findByLabelText(/Add a tag/);
        type(input, 'left behind');
        fireEvent.blur(input);
        expect(latest.topics.tags).toEqual(['left behind']);
    });

    it('refuses a repeat, ignoring case, and says so', async () => {
        show(topics, TagsField, { topics: { type: 'tags', tags: ['Vegan'] } });
        const input = await screen.findByLabelText(/Add a tag/);
        type(input, 'vegan');
        press(input, 'Enter');
        expect(latest.topics.tags).toEqual(['Vegan']);
        expect(screen.getByRole('status')).toHaveTextContent('\u201cvegan\u201d is already added.');
        expect(input).toHaveValue('vegan');
    });

    it('refuses a tag longer than the question allows, and one past the most tags', async () => {
        show(topics, TagsField, { topics: { type: 'tags', tags: ['a', 'b', 'c'] } });
        const input = await screen.findByLabelText(/Add a tag/);
        type(input, 'd');
        press(input, 'Enter');
        expect(latest.topics.tags).toEqual(['a', 'b', 'c']);
        expect(screen.getByRole('status')).toHaveTextContent('You can add at most 3 tags.');
        type(input, 'x'.repeat(13));
        press(input, 'Enter');
        expect(screen.getByRole('status')).toHaveTextContent('Keep each tag to 12 characters or fewer.');
    });

    it('shows the chips with a remove button named after the tag, and removes it', async () => {
        show(topics, TagsField, { topics: { type: 'tags', tags: ['vegan', 'halal'] } });
        const remove = await screen.findByRole('button', { name: 'Remove vegan' });
        fireEvent.click(remove);
        expect(latest.topics.tags).toEqual(['halal']);
        expect(screen.getByRole('status')).toHaveTextContent('Removed \u201cvegan\u201d. 1 tag left.');
        expect(screen.getByLabelText(/Add a tag/)).toHaveFocus();
        fireEvent.click(screen.getByRole('button', { name: 'Remove halal' }));
        expect(latest.topics).toBeUndefined();
    });

    it('removes the last tag with Backspace in the empty box, and not while there is text', async () => {
        show(topics, TagsField, { topics: { type: 'tags', tags: ['a', 'b'] } });
        const input = await screen.findByLabelText(/Add a tag/);
        type(input, 'x');
        press(input, 'Backspace');
        expect(latest.topics.tags).toEqual(['a', 'b']);
        type(input, '');
        press(input, 'Backspace');
        expect(latest.topics.tags).toEqual(['a']);
    });

    it('announces what it added, politely and unseen', async () => {
        show(topics, TagsField);
        const input = await screen.findByLabelText(/Add a tag/);
        type(input, 'vegan');
        press(input, 'Enter');
        const status = screen.getByRole('status');
        expect(status).toHaveTextContent('Added \u201cvegan\u201d. 1 tag in total.');
        expect(status).toHaveClass('sr-only');
    });

    it('counts "n of max" when the question has a most, and asks for the fewest otherwise', async () => {
        show(topics, TagsField, { topics: { type: 'tags', tags: ['a', 'b'] } });
        expect(await screen.findByText('2 of 3 tags')).toBeInTheDocument();
        show(plainTags, TagsField);
        expect(await screen.findAllByText(/Enter at least 2 tags\./)).not.toHaveLength(0);
    });

    it('is the same shape the server checks: tags in the answer are trimmed, different and well formed', async () => {
        show(topics, TagsField);
        const input = await screen.findByLabelText(/Add a tag/);
        for (const tag of ['One', ' two ', 'ONE', 'three;', 'f,our']) {
            type(input, tag);
            press(input, 'Enter');
        }
        expect(checkAnswerRules(topics, latest.topics)).toEqual([]);
    });

    it('writes its text in Dutch', async () => {
        window.history.pushState({}, '', '/?lang=nl');
        try {
            show(topics, TagsField, { topics: { type: 'tags', tags: ['vegan'] } });
            expect(await screen.findByRole('button', { name: 'Verwijder vegan' })).toBeInTheDocument();
            expect(screen.getByLabelText(/Voeg een tag toe/)).toBeInTheDocument();
            expect(screen.getByText('1 van 3 tags')).toBeInTheDocument();
        } finally {
            window.history.pushState({}, '', '/');
        }
    });

    it('passes axe, with and without tags and with a refusal showing', async () => {
        const { container } = show(topics, TagsField, { topics: { type: 'tags', tags: ['vegan'] } });
        const input = await screen.findByLabelText(/Add a tag/);
        type(input, 'VEGAN');
        press(input, 'Enter');
        await screen.findByText(/already added/);
        const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => v.id)).toEqual([]);
    });
});
