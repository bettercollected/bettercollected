'use client';

import { useState } from 'react';

import { RefreshCw, Sparkles } from 'lucide-react';

import { AIOptIn, aiErrorMessage, isAINotEnabledError, useWorkspaceAI } from '@app/components/ai/ai-consent';
import { Button } from '@app/shadcn/components/ui/button';
import { selectIsAdmin } from '@app/store/auth/slice';
import { selectForm, setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGenerateAIInsightsMutation, useGetAIInsightsQuery, useUpdateAIInsightsSettingsMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

// What a summary sends (backend services/ai/insights.py project_responses).
const INSIGHTS_SENDS = "this form's questions and the answers of responses submitted since AI insights were allowed, including free-text answers as written; email and phone answers are replaced by a placeholder and staff-only fields are left out";

interface InsightTheme {
    title: string;
    description: string;
    approxCount?: number | null;
}

interface Insight {
    summary: string;
    themes: InsightTheme[];
    actionable: string[];
    sentiment?: string | null;
    responseCount: number;
    totalResponses: number;
    generatedAt: string;
    analysedSince?: string | null;
}

/**
 * AI summary of a form's responses (plan §2 'response summaries', P3).
 * Needs the workspace AI opt-in (#715) and the form's own "Allow AI insights
 * on responses" (#716, admins only): while that is on, respondents see a
 * notice naming the provider, and only responses submitted afterwards are
 * analysed. The AI reads answer content ONLY when an admin clicks Summarize;
 * free-text answers are sent as written, and the copy says so.
 */
export default function AIInsightsCard() {
    const dispatch = useAppDispatch();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const isAdmin = useAppSelector(selectIsAdmin);
    const { data: cached } = useGetAIInsightsQuery({ workspaceId: workspace?.id, formId: form?.formId }, { skip: !workspace?.id || !form?.formId || !isAdmin });
    const [generate, { isLoading: isGenerating }] = useGenerateAIInsightsMutation();
    const [updateSettings, { isLoading: isUpdating }] = useUpdateAIInsightsSettingsMutation();
    const [fresh, setFresh] = useState<Insight | null>(null);
    const [error, setError] = useState<string | null>(null);
    const { settings: aiSettings, enabled: aiEnabled, providerName: workspaceProvider, refetch: refetchAISettings } = useWorkspaceAI();

    const formAllows = !!form?.settings?.aiInsightsEnabled;
    // the provider respondents were told about
    const providerName = (formAllows && form?.settings?.aiInsightsProviderName) || workspaceProvider;
    const allowedSince = form?.settings?.aiInsightsEnabledAt;
    const insight: Insight | null = fresh ?? cached ?? null;

    const handleGenerate = async () => {
        setError(null);
        const response: any = await generate({ workspaceId: workspace.id, formId: form.formId });
        if (response.data) {
            setFresh(response.data);
        } else {
            if (isAINotEnabledError(response.error)) refetchAISettings();
            setError(aiErrorMessage(response.error, 'Could not generate the summary — please try again.'));
        }
    };

    const setAllowed = async (enabled: boolean) => {
        setError(null);
        const response: any = await updateSettings({ workspaceId: workspace.id, formId: form.formId, enabled });
        if (response.data) {
            dispatch(
                setFormSettings({
                    ...(form?.settings ?? {}),
                    aiInsightsEnabled: response.data.enabled,
                    aiInsightsProvider: response.data.provider ?? null,
                    aiInsightsProviderName: response.data.providerName ?? null,
                    aiInsightsEnabledBy: response.data.enabledBy ?? null,
                    aiInsightsEnabledAt: response.data.enabledAt ?? null
                })
            );
        } else {
            setError(aiErrorMessage(response.error, 'Could not save. Please try again.'));
        }
    };

    if (!isAdmin) {
        return (
            <div className="mb-6 flex flex-col gap-2 rounded-lg border border-black-200 bg-white p-5">
                <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-brand-500" />
                    <h2 className="text-sm font-semibold text-black-900">AI summary</h2>
                </div>
                <p className="text-[13px] text-black-600">Only workspace admins can run AI summaries of responses.</p>
            </div>
        );
    }

    return (
        <div className="mb-6 flex flex-col gap-3 rounded-lg border border-black-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-brand-500" />
                    <h2 className="text-sm font-semibold text-black-900">AI summary</h2>
                </div>
                {insight && aiEnabled && formAllows && (
                    <button type="button" disabled={isGenerating} onClick={handleGenerate} className="flex items-center gap-1 text-xs text-black-500 transition-colors disabled:opacity-60 hover:text-black-800">
                        <RefreshCw className={`h-3 w-3 ${isGenerating ? 'animate-spin' : ''}`} />
                        {isGenerating ? 'Summarizing…' : 'Refresh'}
                    </button>
                )}
            </div>

            {aiSettings && !aiEnabled && !insight ? (
                <AIOptIn feature="The AI summary" sends={INSIGHTS_SENDS} compact />
            ) : aiEnabled && !formAllows ? (
                <div className="flex flex-col items-start gap-2.5">
                    <p className="max-w-[68ch] text-[13px] leading-relaxed text-black-600">
                        AI summaries are off for this form. When you allow them, respondents see a notice that their responses may be analysed by an AI provider ({workspaceProvider}), and only responses submitted from then on are ever sent. Responses
                        already collected are not analysed.
                    </p>
                    {error && <p className="text-xs text-[#7A2E2E]">{error}</p>}
                    <Button size="sm" variant="v2Button" isLoading={isUpdating} onClick={() => setAllowed(true)}>
                        Allow AI insights on responses
                    </Button>
                </div>
            ) : !insight ? (
                <div className="flex flex-col items-start gap-2.5">
                    <p className="max-w-[68ch] text-[13px] leading-relaxed text-black-600">
                        Get a plain-language summary of what your responses say — recurring themes, overall tone, and what to act on. Answers are sent to {providerName} <span className="font-medium">only when you click</span>, and only for responses
                        submitted
                        {allowedSince ? ` since ${new Date(allowedSince).toLocaleString()}` : ' since AI insights were allowed'}, when respondents started seeing the notice. Free-text answers are sent as written, so anything respondents typed into them
                        (names, addresses, health details) reaches {providerName}. Respondent identities are not sent, email and phone answers are replaced by a placeholder, and staff-only fields are left out.
                    </p>
                    {error && <p className="text-xs text-[#7A2E2E]">{error}</p>}
                    <div className="flex flex-wrap items-center gap-3">
                        <Button size="sm" variant="v2Button" isLoading={isGenerating} disabled={!aiEnabled} onClick={handleGenerate}>
                            Summarize responses
                        </Button>
                        <button type="button" disabled={isUpdating} onClick={() => setAllowed(false)} className="text-xs text-black-500 underline decoration-dotted underline-offset-2 hover:text-black-800">
                            Stop allowing AI insights
                        </button>
                    </div>
                </div>
            ) : (
                <div className="flex flex-col gap-3">
                    <p className="max-w-[75ch] text-[13px] leading-relaxed text-black-800">{insight.summary}</p>
                    {!!insight.themes?.length && (
                        <ul className="flex flex-col gap-1.5">
                            {insight.themes.map((theme) => (
                                <li key={theme.title} className="flex items-baseline gap-2 text-[13px]">
                                    <span className="shrink-0 font-medium text-black-900">{theme.title}</span>
                                    {typeof theme.approxCount === 'number' && <span className="shrink-0 rounded bg-black-100 px-1.5 py-0.5 text-[10.5px] tabular-nums text-black-600">~{theme.approxCount}</span>}
                                    <span className="text-black-600">{theme.description}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                    {!!insight.actionable?.length && (
                        <div className="text-[13px]">
                            <span className="font-medium text-black-900">Worth acting on: </span>
                            <span className="text-black-700">{insight.actionable.join(' · ')}</span>
                        </div>
                    )}
                    {insight.sentiment && <p className="text-xs text-black-500">{insight.sentiment}</p>}
                    {error && <p className="text-xs text-[#7A2E2E]">{error}</p>}
                    <p className="text-[10.5px] text-black-400">
                        Based on {insight.responseCount === insight.totalResponses ? `all ${insight.totalResponses}` : `${insight.responseCount} of ${insight.totalResponses}`} responses
                        {insight.analysedSince ? ` (submitted since ${new Date(insight.analysedSince).toLocaleString()})` : ''} · generated {new Date(insight.generatedAt).toLocaleString()} · sent to {providerName}: {INSIGHTS_SENDS}
                    </p>
                </div>
            )}
        </div>
    );
}
