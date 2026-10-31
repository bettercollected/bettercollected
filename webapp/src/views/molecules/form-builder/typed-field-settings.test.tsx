// Builder text resolves through the app's i18n instance.
import '@app/shared/hocs/i18n-provider';
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';

import AnswerRulesSettings from './answer-rules-settings';

vi.mock('@app/store/redux/form-api', async (importOriginal) => ({ ...(await importOriginal<typeof import('@app/store/redux/form-api')>()), useCheckAnswerPatternMutation: () => [vi.fn(), {}] }));

const time = (properties: Record<string, any> = {}): StandardFormFieldDto => ({ id: 't', index: 0, type: FieldTypes.TIME, title: 'Arrival', properties });
const money = (properties: Record<string, any> = {}, validations: Record<string, any> = {}): StandardFormFieldDto => ({ id: 'c', index: 0, type: FieldTypes.CURRENCY, title: 'Budget', properties, validations });

function setup(field: StandardFormFieldDto) {
    const onChange = vi.fn();
    const onPropertyChange = vi.fn();
    render(<AnswerRulesSettings field={field} onChange={onChange} onPropertyChange={onPropertyChange} />);
    return { onChange, onPropertyChange };
}

afterEach(async () => {
    await act(() => i18n.changeLanguage('en'));
});

describe('settings of a time question', () => {
    it('sets and clears the earliest and latest time', () => {
        const { onPropertyChange } = setup(time({ minTime: '08:00' }));
        const earliest = screen.getByLabelText('Earliest time');
        expect(earliest).toHaveValue('08:00');
        fireEvent.change(screen.getByLabelText('Latest time'), { target: { value: '17:30' } });
        expect(onPropertyChange).toHaveBeenLastCalledWith({ maxTime: '17:30' });
        fireEvent.change(earliest, { target: { value: '' } });
        expect(onPropertyChange).toHaveBeenLastCalledWith({ minTime: undefined });
    });

    it('says when the window is back to front', () => {
        setup(time({ minTime: '18:00', maxTime: '08:00' }));
        expect(screen.getByLabelText('Earliest time')).toBeInvalid();
        expect(screen.getByRole('status')).toHaveTextContent('The earliest time is after the latest time.');
    });

    it('saves the label when the box is left', () => {
        const { onPropertyChange } = setup(time());
        const label = screen.getByLabelText('Label');
        fireEvent.change(label, { target: { value: ' Arrival time ' } });
        expect(onPropertyChange).not.toHaveBeenCalled();
        fireEvent.blur(label);
        expect(onPropertyChange).toHaveBeenCalledWith({ label: 'Arrival time' });
    });

    it('is in Dutch for the Dutch builder', async () => {
        await act(() => i18n.changeLanguage('nl'));
        setup(time());
        expect(screen.getByLabelText('Vroegste tijd')).toBeInTheDocument();
        expect(screen.getByLabelText('Laatste tijd')).toBeInTheDocument();
    });
});

describe('settings of a currency question', () => {
    it('lists the currencies, the first being the default, and adds one', () => {
        const { onPropertyChange } = setup(money({ currencies: ['EUR', 'GBP'] }));
        const list = screen.getByRole('list', { name: 'Currencies' });
        const items = within(list).getAllByRole('listitem');
        expect(items.map((item) => item.textContent)).toEqual(['EURDefault', 'GBP']);
        fireEvent.change(screen.getByRole('combobox', { name: 'Add a currency' }), { target: { value: 'USD' } });
        expect(onPropertyChange).toHaveBeenLastCalledWith({ currencies: ['EUR', 'GBP', 'USD'] });
    });

    it('makes another currency the default, and removes one', () => {
        const { onPropertyChange } = setup(money({ currencies: ['EUR', 'GBP'] }));
        fireEvent.click(screen.getByRole('button', { name: 'Make GBP the default' }));
        expect(onPropertyChange).toHaveBeenLastCalledWith({ currencies: ['GBP', 'EUR'] });
        fireEvent.click(screen.getByRole('button', { name: 'Remove GBP' }));
        expect(onPropertyChange).toHaveBeenLastCalledWith({ currencies: ['EUR'] });
    });

    it('offers the euro alone when none is chosen, and does not let the last one go', () => {
        setup(money());
        expect(screen.getAllByRole('listitem')).toHaveLength(1);
        expect(screen.queryByRole('button', { name: /Remove/ })).toBeNull();
    });

    it('limits the amount', () => {
        const { onChange } = setup(money({}, { minValue: 5 }));
        expect(screen.getByLabelText('Lowest amount')).toHaveValue(5);
        fireEvent.change(screen.getByLabelText('Highest amount'), { target: { value: '99.5' } });
        expect(onChange).toHaveBeenLastCalledWith({ maxValue: 99.5 });
    });

    it('says when the lowest amount is above the highest', () => {
        setup(money({}, { minValue: 100, maxValue: 10 }));
        expect(screen.getByRole('status')).toHaveTextContent('The lowest amount is more than the highest.');
    });

    it('is in Dutch for the Dutch builder', async () => {
        await act(() => i18n.changeLanguage('nl'));
        setup(money({ currencies: ['EUR', 'GBP'] }));
        expect(screen.getByRole('list', { name: 'Valuta' })).toBeInTheDocument();
        expect(screen.getByLabelText('Laagste bedrag')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Maak GBP de standaard' })).toBeInTheDocument();
    });
});

describe('a day question', () => {
    it('has no answer rules of its own (only date rules)', () => {
        const { container } = render(<AnswerRulesSettings field={{ id: 'd', index: 0, type: FieldTypes.DAY, title: 'Born', properties: {} }} onChange={() => undefined} />);
        expect(container).toBeEmptyDOMElement();
    });
});
