import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const cachedQueryMock: { data: any } = { data: undefined };
const generateMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetAIInsightsQuery: () => cachedQueryMock,
        useGenerateAIInsightsMutation: () => [generateMock, { isLoading: false }]
    };
});

import { store } from '@app/store/store';
import AIInsightsCard from './ai-insights-card';

const INSIGHT = {
    summary: 'Respondents love onboarding but find billing confusing.',
    themes: [{ title: 'Billing confusion', description: 'Invoices are unclear.', approxCount: 2 }],
    actionable: ['Clarify the invoice layout.'],
    sentiment: 'Mostly positive.',
    responseCount: 3,
    totalResponses: 3,
    generatedAt: '2026-07-09T12:00:00Z'
};

const renderCard = () =>
    render(
        <ReduxProvider store={store}>
            <AIInsightsCard />
        </ReduxProvider>
    );

describe('AIInsightsCard', () => {
    beforeEach(() => {
        generateMock.mockReset();
        cachedQueryMock.data = undefined;
    });

    it('empty state states the opt-in contract and offers one explicit action', () => {
        renderCard();
        expect(screen.getByText(/only when you click/)).toBeDefined();
        expect(screen.getByRole('button', { name: /Summarize responses/ })).toBeDefined();
    });

    it('generating renders summary, themes with counts, and provenance', async () => {
        generateMock.mockResolvedValue({ data: INSIGHT });
        renderCard();

        fireEvent.click(screen.getByRole('button', { name: /Summarize responses/ }));
        await waitFor(() => expect(screen.getByText(/love onboarding/)).toBeDefined());
        expect(screen.getByText('Billing confusion')).toBeDefined();
        expect(screen.getByText('~2')).toBeDefined();
        expect(screen.getByText(/Clarify the invoice layout/)).toBeDefined();
        expect(screen.getByText(/all 3 responses/)).toBeDefined();
        expect(screen.getByText(/never shared with the AI/)).toBeDefined();
    });

    it('a cached insight renders without any generate call', () => {
        cachedQueryMock.data = INSIGHT;
        renderCard();
        expect(screen.getByText(/love onboarding/)).toBeDefined();
        expect(generateMock).not.toHaveBeenCalled();
        // Regeneration stays available.
        expect(screen.getByRole('button', { name: /Refresh/ })).toBeDefined();
    });

    it('errors are stated honestly in place', async () => {
        generateMock.mockResolvedValue({ error: { status: 400, data: 'This form has no responses to summarize yet.' } });
        renderCard();

        fireEvent.click(screen.getByRole('button', { name: /Summarize responses/ }));
        await waitFor(() => expect(screen.getByText(/no responses to summarize/)).toBeDefined());
    });
});
