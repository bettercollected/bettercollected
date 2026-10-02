'use client';

import { useState } from 'react';

import { RefreshCw, Sparkles } from 'lucide-react';

import { AIOptIn, aiErrorMessage, isAINotEnabledError, useWorkspaceAI } from '@app/components/ai/ai-consent';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGenerateAIInsightsMutation, useGetAIInsightsQuery } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

// What a summary sends (backend services/ai/insights.py project_responses).
const INSIGHTS_SENDS = "this form's questions and the answers of its responses, including free-text answers as written; email and phone answers are replaced by a placeholder";

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
}

/**
 * AI summary of a form's responses (plan §2 'response summaries', P3).
 * Opt-in by construction: the AI reads answer content ONLY when the creator
 * clicks Summarize — viewing later reads the cached result. Respondent
 * identities and email/phone values are not sent; free-text answers are
 * sent as written, and the copy says so (#716).
 */
export default function AIInsightsCard() {
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const { data: cached } = useGetAIInsightsQuery({ workspaceId: workspace?.id, formId: form?.formId }, { skip: !workspace?.id || !form?.formId });
    const [generate, { isLoading: isGenerating }] = useGenerateAIInsightsMutation();
    const [fresh, setFresh] = useState<Insight | null>(null);
    const [error, setError] = useState<string | null>(null);
    const { settings: aiSettings, enabled: aiEnabled, providerName, refetch: refetchAISettings } = useWorkspaceAI();

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

    return (
        <div className="mb-6 flex flex-col gap-3 rounded-lg border border-black-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-brand-500" />
                    <h2 className="text-sm font-semibold text-black-900">AI summary</h2>
                </div>
                {insight && aiEnabled && (
                    <button type="button" disabled={isGenerating} onClick={handleGenerate} className="flex items-center gap-1 text-xs text-black-500 transition-colors disabled:opacity-60 hover:text-black-800">
                        <RefreshCw className={`h-3 w-3 ${isGenerating ? 'animate-spin' : ''}`} />
                        {isGenerating ? 'Summarizing…' : 'Refresh'}
                    </button>
                )}
            </div>

            {aiSettings && !aiEnabled && !insight ? (
                <AIOptIn feature="The AI summary" sends={INSIGHTS_SENDS} compact />
            ) : !insight ? (
                <div className="flex flex-col items-start gap-2.5">
                    <p className="max-w-[68ch] text-[13px] leading-relaxed text-black-600">
                        Get a plain-language summary of what your responses say — recurring themes, overall tone, and what to act on. Answers are sent to {providerName} <span className="font-medium">only when you click</span>. Free-text answers are sent as
                        written, so anything respondents typed into them (names, addresses, health details) reaches {providerName}. Respondent identities are not sent, and email and phone answers are replaced by a placeholder.
                    </p>
                    {error && <p className="text-xs text-[#7A2E2E]">{error}</p>}
                    <Button size="sm" variant="v2Button" isLoading={isGenerating} onClick={handleGenerate}>
                        Summarize responses
                    </Button>
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
                        Based on {insight.responseCount === insight.totalResponses ? `all ${insight.totalResponses}` : `the latest ${insight.responseCount} of ${insight.totalResponses}`} responses · generated{' '}
                        {new Date(insight.generatedAt).toLocaleString()} · sent to {providerName}: {INSIGHTS_SENDS}
                    </p>
                </div>
            )}
        </div>
    );
}
