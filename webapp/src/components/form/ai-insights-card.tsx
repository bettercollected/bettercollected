'use client';

import { useState } from 'react';

import { RefreshCw, Sparkles } from 'lucide-react';

import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGenerateAIInsightsMutation, useGetAIInsightsQuery } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

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
 * clicks Summarize — viewing later reads the cached result. Identities and
 * email/phone values are never sent to the model at all.
 */
export default function AIInsightsCard() {
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const { data: cached } = useGetAIInsightsQuery({ workspaceId: workspace?.id, formId: form?.formId }, { skip: !workspace?.id || !form?.formId });
    const [generate, { isLoading: isGenerating }] = useGenerateAIInsightsMutation();
    const [fresh, setFresh] = useState<Insight | null>(null);
    const [error, setError] = useState<string | null>(null);

    const insight: Insight | null = fresh ?? cached ?? null;

    const handleGenerate = async () => {
        setError(null);
        const response: any = await generate({ workspaceId: workspace.id, formId: form.formId });
        if (response.data) {
            setFresh(response.data);
        } else {
            setError(typeof response.error?.data === 'string' ? response.error.data : 'Could not generate the summary — please try again.');
        }
    };

    return (
        <div className="border-black-200 mb-6 flex flex-col gap-3 rounded-lg border bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <Sparkles className="text-brand-500 h-4 w-4" />
                    <h2 className="text-black-900 text-sm font-semibold">AI summary</h2>
                </div>
                {insight && (
                    <button type="button" disabled={isGenerating} onClick={handleGenerate} className="text-black-500 hover:text-black-800 flex items-center gap-1 text-xs transition-colors disabled:opacity-60">
                        <RefreshCw className={`h-3 w-3 ${isGenerating ? 'animate-spin' : ''}`} />
                        {isGenerating ? 'Summarizing…' : 'Refresh'}
                    </button>
                )}
            </div>

            {!insight ? (
                <div className="flex flex-col items-start gap-2.5">
                    <p className="text-black-600 max-w-[68ch] text-[13px] leading-relaxed">
                        Get a plain-language summary of what your responses say — recurring themes, overall tone, and what to act on. The AI reads answer content <span className="font-medium">only when you click</span>; respondent identities, emails and phone
                        numbers are never shared with it.
                    </p>
                    {error && <p className="text-xs text-[#7A2E2E]">{error}</p>}
                    <Button size="sm" variant="v2Button" isLoading={isGenerating} onClick={handleGenerate}>
                        Summarize responses
                    </Button>
                </div>
            ) : (
                <div className="flex flex-col gap-3">
                    <p className="text-black-800 max-w-[75ch] text-[13px] leading-relaxed">{insight.summary}</p>
                    {!!insight.themes?.length && (
                        <ul className="flex flex-col gap-1.5">
                            {insight.themes.map((theme) => (
                                <li key={theme.title} className="flex items-baseline gap-2 text-[13px]">
                                    <span className="text-black-900 shrink-0 font-medium">{theme.title}</span>
                                    {typeof theme.approxCount === 'number' && <span className="bg-black-100 text-black-600 shrink-0 rounded px-1.5 py-0.5 text-[10.5px] tabular-nums">~{theme.approxCount}</span>}
                                    <span className="text-black-600">{theme.description}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                    {!!insight.actionable?.length && (
                        <div className="text-[13px]">
                            <span className="text-black-900 font-medium">Worth acting on: </span>
                            <span className="text-black-700">{insight.actionable.join(' · ')}</span>
                        </div>
                    )}
                    {insight.sentiment && <p className="text-black-500 text-xs">{insight.sentiment}</p>}
                    {error && <p className="text-xs text-[#7A2E2E]">{error}</p>}
                    <p className="text-black-400 text-[10.5px]">
                        Based on {insight.responseCount === insight.totalResponses ? `all ${insight.totalResponses}` : `the latest ${insight.responseCount} of ${insight.totalResponses}`} responses · generated {new Date(insight.generatedAt).toLocaleString()} · identities
                        and contact details are never shared with the AI
                    </p>
                </div>
            )}
        </div>
    );
}
