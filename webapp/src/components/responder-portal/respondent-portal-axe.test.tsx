// The respondent's own views of a submission pass axe (WCAG 2.0/2.1 A and AA):
// the organisation's feedback on it and finding it by its number.
// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { axeViolations } from '@app/test/axe';

import RespondentFeedbackSection from './respondent-feedback-section';
import SearchBySubmissionNumber from './search-by-submission-number';

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/store/workspaces/api', async (importOriginal) => ({
    ...(await importOriginal<typeof import('@app/store/workspaces/api')>()),
    // No submission has this number.
    useLazyGetWorkspaceSubmissionByUUIDQuery: () => [async () => ({ error: { status: 404 } }), { isLoading: false }]
}));

describe('respondent portal views pass axe', () => {
    it('feedback with a status and updates', async () => {
        const { container } = render(
            <RespondentFeedbackSection
                feedback={{
                    author: 'Acme',
                    currentStatus: 'Selected',
                    entries: [
                        { status: 'Under review', message: 'Thanks, we are looking at it', createdAt: '2026-10-01T10:00:00Z' },
                        { status: null, message: 'Please bring your passport', createdAt: '2026-10-03T10:00:00Z' }
                    ]
                }}
            />
        );
        expect(await axeViolations(container)).toEqual([]);
    });

    it('feedback with nothing yet', async () => {
        const { container } = render(<RespondentFeedbackSection feedback={{ entries: [] }} workspaceTitle="Acme" />);
        expect(await axeViolations(container)).toEqual([]);
    });

    it('finding a submission by its number, and the error when none matches', async () => {
        const { container } = render(
            <ReduxProvider store={store}>
                <SearchBySubmissionNumber />
            </ReduxProvider>
        );
        expect(await axeViolations(container)).toEqual([]);

        const input = screen.getByRole('textbox', { name: 'Submission number' });
        fireEvent.change(input, { target: { value: 'not-a-number' } });
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Search' })));
        expect(await screen.findByText(/does not match/)).toBeInTheDocument();
        expect(input).toHaveAttribute('aria-invalid', 'true');
        expect(input).toHaveAccessibleDescription(/does not match with any form responses/);
        expect(await axeViolations(container)).toEqual([]);
    });
});

describe('the submission-number search speaks the reader’s language', () => {
    afterEach(() => window.history.replaceState(null, '', '/'));
    const renderSearch = (audience?: 'respondent' | 'team') =>
        render(
            <ReduxProvider store={store}>
                <SearchBySubmissionNumber audience={audience} />
            </ReduxProvider>
        );

    it("is in the respondent's language on their pages, error included", async () => {
        window.history.replaceState(null, '', '/acme/my-submissions?lang=nl');
        const { container } = renderSearch();
        expect(await screen.findByText('Zoek een inzending op nummer')).toBeInTheDocument();
        expect(container.querySelector('form')).toHaveAttribute('lang', 'nl');
        const input = screen.getByRole('textbox', { name: 'Inzendnummer' });
        expect(input).toHaveAttribute('placeholder', 'Vul het inzendnummer in');
        fireEvent.change(input, { target: { value: 'not-a-number' } });
        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Zoeken' })));
        expect(input).toHaveAccessibleDescription('Er is geen inzending met dit nummer.');
    });

    it("stays in the app's language on the team's dashboard", async () => {
        window.history.replaceState(null, '', '/acme/dashboard?lang=nl');
        const { container } = renderSearch('team');
        expect(await screen.findByText('Find a response by its number')).toBeInTheDocument();
        expect(container.querySelector('form')).toHaveAttribute('lang', 'en');
    });
});
