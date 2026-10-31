import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';

import { OpenDateControl, ResponseLimitControl } from './form-availability-controls';

const typeInto = (testId: string, value: string) => fireEvent.change(screen.getByTestId(testId), { target: { value } });
const click = async (name: string) => act(async () => void fireEvent.click(screen.getByRole('button', { name })));

describe('the open date setting', () => {
    it('saves the typed local time as a UTC instant, only when asked', async () => {
        const onSave = vi.fn().mockResolvedValue(undefined);
        render(<OpenDateControl onSave={onSave} aria-labelledby="t" />);
        const save = screen.getByRole('button', { name: 'Save date' }) as HTMLButtonElement;
        expect(save.disabled).toBe(true);
        expect(screen.queryByRole('button', { name: 'Remove date' })).toBeNull();

        typeInto('open-date-input', '2026-11-02T09:00');
        expect(onSave).not.toHaveBeenCalled();
        expect(save.disabled).toBe(false);
        await click('Save date');
        expect(onSave).toHaveBeenCalledTimes(1);
        expect(onSave.mock.calls[0][0]).toMatch(/^2026-11-02T\d{2}:00:00\.000Z$/);
    });

    it('names its time zone, and the field is named by the row', () => {
        render(<OpenDateControl onSave={vi.fn()} aria-labelledby="row-title" aria-describedby="row-description" />);
        const input = screen.getByTestId('open-date-input');
        expect(input.getAttribute('aria-labelledby')).toBe('row-title');
        expect(input.getAttribute('aria-describedby')).toContain('row-description');
        expect(document.body.textContent).toMatch(/Entered in your time zone \(.+\)\. Respondents see it in theirs\./);
    });

    it('removes a stored date with an empty value', async () => {
        const onSave = vi.fn().mockResolvedValue(undefined);
        render(<OpenDateControl value="2026-11-02T08:00:00+00:00" onSave={onSave} />);
        expect((screen.getByTestId('open-date-input') as HTMLInputElement).value).toMatch(/^2026-11-02T\d{2}:00$/);
        await click('Remove date');
        expect(onSave).toHaveBeenCalledWith('');
    });

    it('refuses a date that is not before the close date, and says so', () => {
        const onSave = vi.fn();
        render(<OpenDateControl closeDate="2026-11-09T08:00:00+00:00" onSave={onSave} />);
        typeInto('open-date-input', '2026-11-20T09:00');
        expect(screen.getByRole('alert').textContent).toBe('The open date must be before the close date.');
        expect((screen.getByRole('button', { name: 'Save date' }) as HTMLButtonElement).disabled).toBe(true);
        expect(screen.getByTestId('open-date-input').getAttribute('aria-invalid')).toBe('true');
        typeInto('open-date-input', '2026-11-02T09:00');
        expect(screen.queryByRole('alert')).toBeNull();
        expect((screen.getByRole('button', { name: 'Save date' }) as HTMLButtonElement).disabled).toBe(false);
    });

    it('keeps what was typed when the save fails', async () => {
        const onSave = vi.fn().mockResolvedValue({ status: 422 });
        render(<OpenDateControl value="2026-11-02T08:00:00+00:00" onSave={onSave} />);
        await click('Remove date');
        expect((screen.getByTestId('open-date-input') as HTMLInputElement).value).not.toBe('');
    });
});

describe('the response limit setting', () => {
    it('saves a whole number and removes the limit with 0', async () => {
        const onSave = vi.fn().mockResolvedValue(undefined);
        render(<ResponseLimitControl value={100} onSave={onSave} />);
        expect((screen.getByTestId('response-limit-input') as HTMLInputElement).value).toBe('100');
        typeInto('response-limit-input', ' 250 ');
        await click('Save limit');
        expect(onSave).toHaveBeenLastCalledWith(250);
        await click('Remove limit');
        expect(onSave).toHaveBeenLastCalledWith(0);
        expect((screen.getByTestId('response-limit-input') as HTMLInputElement).value).toBe('');
    });

    it.each(['0', '-1', '2.5', 'ten', '1000001'])('refuses %j before it leaves the page', (text) => {
        const onSave = vi.fn();
        render(<ResponseLimitControl onSave={onSave} />);
        typeInto('response-limit-input', text);
        expect(screen.getByRole('alert').textContent).toBe('Enter a whole number from 1 to 1,000,000.');
        expect(screen.getByTestId('response-limit-input').getAttribute('aria-invalid')).toBe('true');
        expect((screen.getByRole('button', { name: 'Save limit' }) as HTMLButtonElement).disabled).toBe(true);
        expect(onSave).not.toHaveBeenCalled();
    });

    it('offers nothing to save while nothing changed, and says editing is not affected', () => {
        render(<ResponseLimitControl value={5} onSave={vi.fn()} aria-labelledby="t" />);
        expect((screen.getByRole('button', { name: 'Save limit' }) as HTMLButtonElement).disabled).toBe(true);
        expect(screen.getByRole('textbox').getAttribute('aria-labelledby')).toBe('t');
        expect(document.body.textContent).toContain('Editing a response is not affected.');
    });
});
