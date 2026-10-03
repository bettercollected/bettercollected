import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import FeedbackStatusesEditor from './feedback-statuses-editor';

describe('FeedbackStatusesEditor', () => {
    it('starts from the defaults and saves the cleaned list', async () => {
        const onSave = vi.fn().mockResolvedValue(undefined);
        render(<FeedbackStatusesEditor onSave={onSave} />);
        expect((screen.getByLabelText('Status 1') as HTMLInputElement).value).toBe('Under review');

        const save = screen.getByRole('button', { name: 'Save statuses' }) as HTMLButtonElement;
        expect(save.disabled).toBe(true);

        fireEvent.click(screen.getByRole('button', { name: 'Add status' }));
        fireEvent.change(screen.getByLabelText('Status 4'), { target: { value: '  Interview  ' } });
        await act(async () => {
            fireEvent.click(save);
        });
        expect(onSave).toHaveBeenCalledWith(['Under review', 'Selected', 'Rejected', 'Interview']);
    });

    it('blocks a duplicate and lets one be removed', () => {
        const onSave = vi.fn();
        render(<FeedbackStatusesEditor statuses={['Open', 'Closed']} onSave={onSave} />);
        fireEvent.change(screen.getByLabelText('Status 2'), { target: { value: 'open' } });
        expect(screen.getByText(/listed twice/)).toBeDefined();
        expect((screen.getByRole('button', { name: 'Save statuses' }) as HTMLButtonElement).disabled).toBe(true);

        fireEvent.click(screen.getByRole('button', { name: 'Remove open' }));
        expect(screen.queryByText(/listed twice/)).toBeNull();
        expect(screen.queryByLabelText('Status 2')).toBeNull();
    });
});
