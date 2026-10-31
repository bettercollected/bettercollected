import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import { DraftRetentionControl } from './form-draft-controls';

const typeDays = (value: string) => fireEvent.change(screen.getByTestId('draft-days-input'), { target: { value } });
const save = async () => act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Save' })));

describe('the days a draft is kept (builder setting)', () => {
    it('saves a whole number from 1 to 90, only when asked', async () => {
        const onSave = vi.fn().mockResolvedValue(undefined);
        render(<DraftRetentionControl onSave={onSave} />);
        const button = screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement;
        expect(button.disabled).toBe(true);
        typeDays('14');
        expect(onSave).not.toHaveBeenCalled();
        expect(button.disabled).toBe(false);
        await save();
        expect(onSave).toHaveBeenCalledWith(14);
    });

    it('shows the default as the placeholder and says what empty means', () => {
        render(<DraftRetentionControl onSave={vi.fn()} />);
        expect((screen.getByTestId('draft-days-input') as HTMLInputElement).placeholder).toBe('30');
        expect(document.body.textContent).toContain('1 to 90 days after the last save. Empty: 30 days. Files are not saved in a draft.');
    });

    it('empties back to the default with 0', async () => {
        const onSave = vi.fn().mockResolvedValue(undefined);
        render(<DraftRetentionControl value={45} onSave={onSave} />);
        expect((screen.getByTestId('draft-days-input') as HTMLInputElement).value).toBe('45');
        typeDays('');
        await save();
        expect(onSave).toHaveBeenCalledWith(0);
    });

    it.each(['0', '91', '1000', '-1', '2.5', 'abc', '1e1'])('refuses %s and says so', (value) => {
        const onSave = vi.fn();
        render(<DraftRetentionControl onSave={onSave} />);
        typeDays(value);
        expect(screen.getByRole('alert').textContent).toBe('Enter a whole number from 1 to 90.');
        expect((screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(true);
        expect(onSave).not.toHaveBeenCalled();
    });

    it('is labelled, and passes axe with and without an error', async () => {
        render(<DraftRetentionControl onSave={vi.fn()} />);
        expect(screen.getByLabelText('Keep drafts for (days)')).toBe(screen.getByTestId('draft-days-input'));
        expect(await axeViolations(document, { page: false })).toEqual([]);
        typeDays('99');
        expect(await axeViolations(document, { page: false })).toEqual([]);
    });
});
