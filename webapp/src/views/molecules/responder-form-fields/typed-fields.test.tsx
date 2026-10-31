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
import DayField from './day-field';
import TimeField from './time-field';

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const time: StandardFormFieldDto = { id: 'arrival', index: 0, type: FieldTypes.TIME, title: 'When do you arrive?', description: 'Doors open early', properties: { minTime: '08:00', maxTime: '17:30' }, validations: { required: true } };
const day: StandardFormFieldDto = { id: 'born', index: 1, type: FieldTypes.DAY, title: 'When were you born?', properties: {} };
const money: StandardFormFieldDto = { id: 'budget', index: 2, type: FieldTypes.CURRENCY, title: 'What is your budget?', properties: { currencies: ['EUR', 'GBP'] } };
const oneCurrency: StandardFormFieldDto = { id: 'fee', index: 3, type: FieldTypes.CURRENCY, title: 'What is the fee?', properties: {} };

let latest: Record<string, any> = {};

function Spy() {
    const { formResponse } = useFormResponse();
    latest = formResponse.answers ?? {};
    return null;
}

const show = (field: StandardFormFieldDto, Component: React.ComponentType<{ field: StandardFormFieldDto }>, answers: Record<string, any> = {}) => {
    store.dispatch(setForm({ formId: 'f', title: 'Typed', fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [time, day, money, oneCurrency] } }] }));
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
        expect(latest.born.date).toBe('0000-02-31');
        expect(checkAnswerRules(day, latest.born)).toEqual(['FORMAT']);
        fireEvent.change(screen.getByLabelText('Year'), { target: { value: '2026' } });
        expect(latest.born.date).toBe('2026-02-31');
        expect(checkAnswerRules(day, latest.born)).toEqual(['FORMAT']);
        fireEvent.change(screen.getByLabelText('Day'), { target: { value: '28' } });
        expect(checkAnswerRules(day, latest.born)).toEqual([]);
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
