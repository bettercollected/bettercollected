import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import i18n from 'i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setForm } from '@app/store/forms/slice';
import '@app/shared/hocs/i18n-provider'; // the catalogue's English text
import { store } from '@app/store/store';

import commonNl from '../../../public/locales/nl/common.json';

import AIInsightsCard from './ai-insights-card';

const cachedQueryMock: { data: any } = { data: undefined };
const generateMock = vi.fn();
const updateInsightsSettingsMock = vi.fn();
vi.mock('@app/store/redux/form-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetAIInsightsQuery: () => cachedQueryMock,
        useGenerateAIInsightsMutation: () => [generateMock, { isLoading: false }],
        useUpdateAIInsightsSettingsMutation: () => [updateInsightsSettingsMock, { isLoading: false }]
    };
});

// Running insights is response.read; allowing them on a form is ai.manage.
const ADMIN_PERMISSIONS = ['response.read', 'ai.manage'];
const access: { permissions: string[] } = { permissions: ADMIN_PERMISSIONS };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => access.permissions.includes(permission), permissions: new Set(access.permissions), isLoading: false })
}));

// Workspace AI opt-in (#715): on unless a test turns it off.
const aiSettingsMock: { data: any; refetch: ReturnType<typeof vi.fn> } = { data: undefined, refetch: vi.fn() };
const updateAISettingsMock = vi.fn();
const updateLearningMock = vi.fn();
const AI_ON = {
    enabled: true,
    provider: 'openai',
    providerName: 'OpenAI',
    defaultProvider: 'openai',
    defaultProviderName: 'OpenAI',
    providers: [{ id: 'openai', name: 'OpenAI', configured: true }],
    canManage: true,
    learnPreferences: false
};
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetAISettingsQuery: () => aiSettingsMock,
        useUpdateAISettingsMutation: () => [updateAISettingsMock, { isLoading: false }]
    };
});

const ALLOWED = { aiInsightsEnabled: true, aiInsightsProvider: 'openai', aiInsightsProviderName: 'OpenAI', aiInsightsEnabledAt: '2026-07-01T09:00:00Z' };
const withFormSettings = (settings: Record<string, any>) => store.dispatch(setForm({ formId: 'form-insights-1', title: 'Feedback', settings }));

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
            <AIInsightsCard defaultOpen />
        </ReduxProvider>
    );

describe('AIInsightsCard', () => {
    beforeEach(() => {
        generateMock.mockReset();
        cachedQueryMock.data = undefined;
        aiSettingsMock.data = { ...AI_ON };
        access.permissions = ADMIN_PERMISSIONS;
        updateInsightsSettingsMock.mockReset();
        withFormSettings({ ...ALLOWED });
    });

    it('is a closed bar until it is opened, and its summary is not even asked for before', () => {
        cachedQueryMock.data = INSIGHT;
        render(
            <ReduxProvider store={store}>
                <AIInsightsCard />
            </ReduxProvider>
        );
        const bar = screen.getByRole('button', { name: 'AI summary' });
        expect(bar).toHaveAttribute('aria-expanded', 'false');
        expect(screen.queryByRole('button', { name: /Refresh/ })).toBeNull();
        fireEvent.click(bar);
        expect(bar).toHaveAttribute('aria-expanded', 'true');
        expect(document.getElementById(bar.getAttribute('aria-controls')!)).toContainElement(screen.getByRole('button', { name: /Refresh/ }));
    });

    it('empty state states the opt-in contract and offers one explicit action', () => {
        renderCard();
        expect(screen.getByText(/only when you click/)).toBeDefined();
        // honest about free text, and names the provider
        expect(screen.getByText(/Free-text answers are sent as/)).toBeDefined();
        expect(screen.getByText(/Answers are sent to OpenAI/)).toBeDefined();
        // #752: only responses whose page showed the notice
        expect(screen.getByText(/submitted from a page that showed the AI notice/)).toBeDefined();
        expect(screen.getByRole('button', { name: /Summarize responses/ })).toBeDefined();
    });

    it('says how many responses were submitted without the AI notice (#752)', () => {
        cachedQueryMock.data = { ...INSIGHT, responseCount: 2, totalResponses: 5, noticeShownResponses: 2 };
        renderCard();
        expect(screen.getByText(/3 of 5 were submitted without the AI notice and are never analysed/)).toBeDefined();
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
        expect(screen.getByText(/sent to OpenAI: .*free-text answers as written/)).toBeDefined();
    });

    it('a cached insight renders without any generate call', () => {
        cachedQueryMock.data = INSIGHT;
        renderCard();
        expect(screen.getByText(/love onboarding/)).toBeDefined();
        expect(generateMock).not.toHaveBeenCalled();
        // Regeneration stays available.
        expect(screen.getByRole('button', { name: /Refresh/ })).toBeDefined();
    });

    it('while AI is off for the workspace, offers the opt-in and no summarize action', () => {
        aiSettingsMock.data = { ...AI_ON, enabled: false, provider: null, providerName: null };
        renderCard();
        expect(screen.getByText('AI is off for this workspace')).toBeDefined();
        expect(screen.queryByRole('button', { name: /Summarize responses/ })).toBeNull();
        expect(generateMock).not.toHaveBeenCalled();
    });

    it('while the form does not allow AI insights, an admin can allow them, and is told what respondents will see', async () => {
        withFormSettings({});
        updateInsightsSettingsMock.mockResolvedValue({ data: { enabled: true, provider: 'openai', providerName: 'OpenAI', enabledAt: '2026-07-10T09:00:00Z' } });
        renderCard();

        expect(screen.getByText(/respondents see a notice/)).toBeDefined();
        expect(screen.getByText(/Responses already collected, and responses from pages opened before you allow it, are never analysed/)).toBeDefined();
        expect(screen.queryByRole('button', { name: /Summarize responses/ })).toBeNull();

        fireEvent.click(screen.getByRole('button', { name: 'Allow AI insights on responses' }));
        await waitFor(() => expect(updateInsightsSettingsMock).toHaveBeenCalledWith(expect.objectContaining({ enabled: true })));
        await waitFor(() => expect(screen.getByRole('button', { name: /Summarize responses/ })).toBeDefined());
        expect(generateMock).not.toHaveBeenCalled();
    });

    it('imported forms cannot get AI insights: their respondents never saw the notice', () => {
        withFormSettings({ provider: 'google' });
        renderCard();
        expect(screen.getByText(/only available for forms collected with BetterCollected/)).toBeDefined();
        expect(screen.queryByRole('button', { name: 'Allow AI insights on responses' })).toBeNull();
        expect(screen.queryByRole('button', { name: /Summarize responses/ })).toBeNull();
    });

    it('members who read responses run insights but do not decide whether the form allows them', () => {
        access.permissions = ['response.read'];
        renderCard();
        expect(screen.getByRole('button', { name: /Summarize responses/ })).toBeDefined();
        expect(screen.queryByText('Stop allowing AI insights')).toBeNull();
    });

    it('members who read responses are told an admin allows insights on a form', () => {
        access.permissions = ['response.read'];
        withFormSettings({});
        renderCard();
        expect(screen.getByText(/A workspace admin can allow them/)).toBeDefined();
        expect(screen.queryByRole('button', { name: 'Allow AI insights on responses' })).toBeNull();
    });

    it('without access to responses there are no insights', () => {
        access.permissions = [];
        renderCard();
        expect(screen.getByText(/Only members who can read this form/)).toBeDefined();
        expect(screen.queryByRole('button', { name: /Summarize responses/ })).toBeNull();
    });

    it('errors are stated honestly in place', async () => {
        generateMock.mockResolvedValue({ error: { status: 400, data: 'This form has no responses to summarize yet.' } });
        renderCard();

        fireEvent.click(screen.getByRole('button', { name: /Summarize responses/ }));
        await waitFor(() => expect(screen.getByText(/no responses to summarize/)).toBeDefined());
    });
});

describe('AIInsightsCard in Dutch', () => {
    beforeEach(async () => {
        cachedQueryMock.data = undefined;
        aiSettingsMock.data = { ...AI_ON };
        access.permissions = ADMIN_PERMISSIONS;
        withFormSettings({ ...ALLOWED });
        i18n.addResourceBundle('nl', 'common', commonNl, true, true);
        await i18n.changeLanguage('nl');
    });
    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    it('says what is sent, to whom and when, in Dutch (formal), with the same facts as the English notice', () => {
        renderCard();
        expect(screen.getByRole('button', { name: 'AI-samenvatting' })).toBeDefined();
        expect(screen.getByText('alleen wanneer u klikt')).toBeDefined();
        const notice = screen.getByText(/Antwoorden worden naar OpenAI gestuurd/);
        // the provider, the notice, the cut-off and what is left out
        expect(notice.textContent).toMatch(/AI-melding stond \(sinds 1 juli 2026 om \d\d:\d\d getoond\)\. Reacties die eerder zijn ingediend/);
        expect(notice.textContent).toMatch(/komt bij OpenAI terecht/);
        expect(notice.textContent).toMatch(/velden voor medewerkers blijven weg/);
        expect(screen.getByRole('button', { name: 'Reacties samenvatten' })).toBeDefined();
        expect(screen.getByRole('button', { name: 'AI-inzichten niet meer toestaan' })).toBeDefined();
    });

    it('says the summary, how many responses it is based on and what was sent, in Dutch', () => {
        cachedQueryMock.data = { ...INSIGHT, responseCount: 2, totalResponses: 5, noticeShownResponses: 2, analysedSince: '2026-07-01T09:00:00Z' };
        renderCard();
        expect(screen.getByRole('button', { name: /Vernieuwen/ })).toBeDefined();
        expect(screen.getByText('Waar u iets mee moet doen:')).toBeDefined();
        const footer = screen.getByText(/^Gebaseerd op 2 van 5 reacties/);
        expect(footer.textContent).toMatch(/\(ingediend met de AI-melding, sinds 1 juli 2026 om \d\d:\d\d getoond\)/);
        expect(footer.textContent).toMatch(/3 van 5 zijn ingediend zonder de AI-melding en worden nooit geanalyseerd/);
        expect(footer.textContent).toMatch(/gemaakt op 9 juli 2026 om \d\d:\d\d/);
        expect(footer.textContent).toMatch(/gestuurd naar OpenAI: de vragen van dit formulier/);
    });

    it('says AI is off for the workspace in Dutch', () => {
        aiSettingsMock.data = { ...AI_ON, enabled: false };
        renderCard();
        expect(screen.getByRole('region', { name: 'AI staat uit voor deze werkruimte' })).toBeDefined();
        expect(screen.getByText(/De AI-samenvatting gebruikt een externe AI-aanbieder/)).toBeDefined();
        expect(screen.getByRole('button', { name: 'AI aanzetten met OpenAI' })).toBeDefined();
    });

    it('says the form has AI summaries off in Dutch', () => {
        withFormSettings({});
        renderCard();
        expect(screen.getByText(/AI-samenvattingen staan uit voor dit formulier/)).toBeDefined();
        expect(screen.getByRole('button', { name: 'AI-inzichten op reacties toestaan' })).toBeDefined();
    });
});
