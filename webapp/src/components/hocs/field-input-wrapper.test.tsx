import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import FieldInputWrapper from './field-input-wrapper';

describe('FieldInputWrapper', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it('reports only typed values, not the value it is given (no edit on mount)', async () => {
        const onChange = vi.fn();
        render(
            <Provider>
                <FieldInputWrapper aria-label="Placeholder" value={undefined} onChange={onChange} />
            </Provider>
        );
        await act(async () => vi.advanceTimersByTimeAsync(1000));
        expect(onChange).not.toHaveBeenCalled();
        fireEvent.change(screen.getByLabelText('Placeholder'), { target: { value: 'Your answer' } });
        await act(async () => vi.advanceTimersByTimeAsync(400));
        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange).toHaveBeenCalledWith('Your answer');
    });

    it('shows a value cleared from outside (an undo), staying controlled', async () => {
        const { rerender } = render(
            <Provider>
                <FieldInputWrapper aria-label="Option" value="Yes" onChange={() => undefined} />
            </Provider>
        );
        rerender(
            <Provider>
                <FieldInputWrapper aria-label="Option" value={undefined} onChange={() => undefined} />
            </Provider>
        );
        await act(async () => vi.advanceTimersByTimeAsync(0));
        expect((screen.getByLabelText('Option') as HTMLInputElement).value).toBe('');
    });
});
