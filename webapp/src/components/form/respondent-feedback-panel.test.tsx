import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StaffFeedback } from '@app/models/dtos/form';
import { store } from '@app/store/store';

import RespondentFeedbackPanel from './respondent-feedback-panel';

const postFeedbackMock = vi.fn();
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        usePostRespondentFeedbackMutation: () => [postFeedbackMock, { isLoading: false }]
    };
});

const STATUSES = ['Under review', 'Selected', 'Rejected'];

const renderPanel = (feedback: StaffFeedback | null, enabled = true) =>
    render(
        <ReduxProvider store={store}>
            <RespondentFeedbackPanel workspaceId="ws1" formId="f1" responseId="r1" feedback={feedback} enabled={enabled} statuses={STATUSES} />
        </ReduxProvider>
    );

describe("RespondentFeedbackPanel (the team's view)", () => {
    beforeEach(() => {
        postFeedbackMock.mockReset();
    });

    it('is hidden while the form has it off and nothing was sent', () => {
        const { container } = renderPanel({ entries: [], canPost: true }, false);
        expect(container.innerHTML).toBe('');
    });

    it('lists the history with who sent each update', () => {
        renderPanel({
            currentStatus: 'Selected',
            entries: [{ id: 'e1', status: 'Selected', message: 'Welcome', createdAt: '2026-10-01T10:00:00Z', createdBy: 'u1', createdByEmail: 'staff@example.com' }],
            canPost: false
        });
        expect(screen.getByText('Welcome')).toBeDefined();
        expect(screen.getByText(/staff@example.com/)).toBeDefined();
        expect(screen.queryByRole('button', { name: 'Send update' })).toBeNull();
        expect(screen.getByText(/can read updates but not send them/)).toBeDefined();
    });

    it('lets admins send a status and a message, and says whether the respondent is emailed', async () => {
        postFeedbackMock.mockResolvedValue({
            data: { currentStatus: 'Selected', entries: [{ id: 'e1', status: 'Selected', message: 'See you Monday', createdByEmail: 'me@example.com', createdAt: '2026-10-02T10:00:00Z' }], canPost: true, notifiesRespondent: true }
        });
        renderPanel({ entries: [], canPost: true, notifiesRespondent: false });
        expect(screen.getByText(/is not emailed/)).toBeDefined();

        const send = screen.getByRole('button', { name: 'Send update' }) as HTMLButtonElement;
        expect(send.disabled).toBe(true);
        fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'Selected' } });
        fireEvent.change(screen.getByLabelText('Message'), { target: { value: '  See you Monday ' } });
        expect(send.disabled).toBe(false);
        await act(async () => {
            fireEvent.click(send);
        });

        expect(postFeedbackMock).toHaveBeenCalledWith({ workspaceId: 'ws1', formId: 'f1', responseId: 'r1', status: 'Selected', message: 'See you Monday' });
        expect(screen.getByText('See you Monday')).toBeDefined();
        expect(screen.getByText(/gets an email that there is an update/)).toBeDefined();
        expect((screen.getByLabelText('Message') as HTMLTextAreaElement).value).toBe('');
    });
});
