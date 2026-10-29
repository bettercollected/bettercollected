import { act, fireEvent, render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';

import AnswerRulesSettings, { PATTERN_CHECK_DELAY_MS } from './answer-rules-settings';

const checkPattern = vi.fn();
vi.mock('@app/store/redux/form-api', async (original) => ({
    ...((await original()) as object),
    useCheckAnswerPatternMutation: () => [checkPattern]
}));

const field = (validations: StandardFormFieldDto['validations'] = {}, type = FieldTypes.SHORT_TEXT): StandardFormFieldDto => ({ id: 'q', index: 0, type, title: 'Name', validations, properties: {} });
const valid = { data: { valid: true, message: null, reason: null } };
const invalid = (reason: string) => ({ data: { valid: false, message: `'x' is not a valid pattern (${reason}).`, reason } });
const box = () => screen.getByLabelText('Regular expression') as HTMLInputElement;

const renderRules = (onChange = vi.fn(), validations: StandardFormFieldDto['validations'] = {}) => {
    render(
        <ReduxProvider store={store}>
            <AnswerRulesSettings field={field(validations)} onChange={onChange} />
        </ReduxProvider>
    );
    return onChange;
};
const type = async (value: string) => {
    act(() => void fireEvent.change(box(), { target: { value } }));
    await act(() => vi.advanceTimersByTimeAsync(PATTERN_CHECK_DELAY_MS));
};

describe('the custom pattern box', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        checkPattern.mockReset().mockResolvedValue(valid);
    });
    afterEach(async () => {
        vi.useRealTimers();
        await act(() => i18n.changeLanguage('en'));
    });

    it('saves a pattern once the server says it can be used', async () => {
        const onChange = renderRules();
        await type('^[A-Z]{3}$');
        expect(checkPattern).toHaveBeenCalledTimes(1);
        expect(onChange).toHaveBeenLastCalledWith({ regex: '^[A-Z]{3}$' });
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it('checks once after typing stops, not on every key', async () => {
        const onChange = renderRules();
        act(() => void fireEvent.change(box(), { target: { value: '^a' } }));
        await act(() => vi.advanceTimersByTimeAsync(PATTERN_CHECK_DELAY_MS - 100));
        await type('^ab');
        expect(checkPattern).toHaveBeenCalledTimes(1);
        expect(checkPattern.mock.calls[0][0].pattern).toBe('^ab');
        expect(onChange).toHaveBeenCalledTimes(1);
    });

    it('shows why a pattern cannot be used, and keeps the one the question has', async () => {
        checkPattern.mockResolvedValue(invalid('invalid perl operator: (?='));
        const onChange = renderRules(vi.fn(), { regex: '^[a-z]+$' });
        await type('^(?=a)b$');
        expect(screen.getByRole('alert')).toHaveTextContent('This pattern cannot be used: invalid perl operator: (?=.');
        expect(screen.getByRole('alert')).toHaveTextContent('no lookarounds and no backreferences');
        expect(screen.getByRole('alert')).toHaveTextContent('The pattern the question already has stays in use until this one is valid.');
        expect(box()).toHaveAttribute('aria-invalid', 'true');
        // nothing was written to the form, the old pattern is not dropped
        expect(onChange).not.toHaveBeenCalled();

        checkPattern.mockResolvedValue(valid);
        await type('^[A-Z]+$');
        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange).toHaveBeenLastCalledWith({ regex: '^[A-Z]+$' });
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it('does not act on a check of a pattern that has been typed over', async () => {
        let first: (value: unknown) => void = () => {};
        checkPattern.mockImplementationOnce(() => new Promise((resolve) => (first = resolve)));
        const onChange = renderRules();
        await type('^a');
        await type('^ab');
        await act(async () => first(valid));
        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange).toHaveBeenLastCalledWith({ regex: '^ab' });
    });

    it('removes the pattern when the box is emptied', async () => {
        const onChange = renderRules(vi.fn(), { regex: '^a$' });
        act(() => void fireEvent.change(box(), { target: { value: '' } }));
        expect(onChange).toHaveBeenLastCalledWith({ regex: undefined });
        expect(checkPattern).not.toHaveBeenCalled();
    });

    it('says so when the pattern could not be checked, and saves nothing', async () => {
        checkPattern.mockResolvedValue({ error: { status: 500 } });
        const onChange = renderRules();
        await type('^a$');
        expect(screen.getByRole('alert')).toHaveTextContent('could not be checked right now');
        expect(onChange).not.toHaveBeenCalled();
    });

    it('speaks Dutch', async () => {
        await act(() => i18n.changeLanguage('nl'));
        checkPattern.mockResolvedValue(invalid('missing ): (a'));
        renderRules();
        await type('(a');
        expect(screen.getByRole('alert')).toHaveTextContent('Dit patroon kan niet worden gebruikt: missing ): (a.');
        expect(screen.getByRole('alert')).toHaveTextContent('RE2-syntaxis');
    });

    it('does not ask the server about a format from the list', async () => {
        renderRules();
        act(() => void fireEvent.change(screen.getByLabelText('Format'), { target: { value: 'iban' } }));
        expect(checkPattern).not.toHaveBeenCalled();
    });
});
