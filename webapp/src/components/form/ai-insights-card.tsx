'use client';

import { useId, useState } from 'react';

import { ChevronDown, RefreshCw, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { AIOptIn, aiErrorMessage, isAINotEnabledError, useWorkspaceAI } from '@app/components/ai/ai-consent';
import { Button } from '@app/shadcn/components/ui/button';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectForm, setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGenerateAIInsightsMutation, useGetAIInsightsQuery, useUpdateAIInsightsSettingsMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { utcToLocalDateTimeIn } from '@app/utils/date-utils';

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
    /** Responses whose page showed the AI notice (#752); absent on older summaries. */
    noticeShownResponses?: number | null;
}

/**
 * AI summary of a form's responses (plan §2 'response summaries', P3).
 * Needs the workspace AI opt-in (#715) and the form's own "Allow AI insights
 * on responses" (#716, ai.manage: admins): while that is on, respondents see
 * a notice naming the provider, and only responses submitted from a page that
 * showed it are analysed (#752: the page sends back the signed notice token;
 * a page opened before the setting was on has none). Running and reading summaries is response.read, like the answers
 * they summarise. The AI reads answer content ONLY when someone clicks
 * Summarize; free-text answers are sent as written, and the copy says so.
 */
function AIInsightsBody() {
    const { t, i18n } = useTranslation();
    // What a summary sends (backend services/ai/insights.py project_responses), in the staff member's language.
    const sends = t('RESPONSES_STAFF.AI_SENDS');
    const when = (value: string) => utcToLocalDateTimeIn(value, i18n.language);
    const dispatch = useAppDispatch();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const { can } = useWorkspacePermissions();
    const canReadResponses = can(WorkspacePermission.RESPONSE_READ);
    const canManageAI = can(WorkspacePermission.AI_MANAGE);
    const { data: cached } = useGetAIInsightsQuery({ workspaceId: workspace?.id, formId: form?.formId }, { skip: !workspace?.id || !form?.formId || !canReadResponses });
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
            setError(aiErrorMessage(response.error, t('RESPONSES_STAFF.AI_ERR_GENERATE')));
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
            setError(aiErrorMessage(response.error, t('RESPONSES_STAFF.AI_ERR_SAVE')));
        }
    };

    // Imported forms (Google Forms, Typeform): respondents answered on the
    // provider's page, which never showed the AI notice (#716).
    const importedForm = !!form?.settings?.provider && form.settings.provider !== 'self';
    if (importedForm) {
        return (
            <div className="flex flex-col gap-2 rounded border border-black-300 bg-white p-5">
                <h2 className="sr-only">{t('RESPONSES_STAFF.AI_SUMMARY')}</h2>
                <p className="max-w-[68ch] text-[13px] text-black-600">{t('RESPONSES_STAFF.AI_IMPORTED')}</p>
            </div>
        );
    }

    if (!canReadResponses) {
        return (
            <div className="flex flex-col gap-2 rounded border border-black-300 bg-white p-5">
                <h2 className="sr-only">{t('RESPONSES_STAFF.AI_SUMMARY')}</h2>
                <p className="text-[13px] text-black-600">{t('RESPONSES_STAFF.AI_NO_READ')}</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-3 rounded border border-black-300 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="sr-only">{t('RESPONSES_STAFF.AI_SUMMARY')}</h2>
                {insight && aiEnabled && formAllows && (
                    <button type="button" disabled={isGenerating} onClick={handleGenerate} className="ml-auto flex items-center gap-1 text-xs text-black-600 transition-colors disabled:opacity-60 hover:text-black-800">
                        <RefreshCw className={`h-3 w-3 ${isGenerating ? 'animate-spin' : ''}`} />
                        {t(isGenerating ? 'RESPONSES_STAFF.AI_SUMMARIZING' : 'RESPONSES_STAFF.AI_REFRESH')}
                    </button>
                )}
            </div>

            {aiSettings && !aiEnabled && !insight ? (
                <AIOptIn feature={t('RESPONSES_STAFF.AI_FEATURE')} sends={sends} compact />
            ) : aiEnabled && !formAllows ? (
                <div className="flex flex-col items-start gap-2.5">
                    <p className="max-w-[68ch] text-[13px] leading-relaxed text-black-600">
                        {t('RESPONSES_STAFF.AI_OFF_FORM', { provider: workspaceProvider })}
                    </p>
                    {error && <p className="text-xs text-[#7A2E2E]">{error}</p>}
                    {canManageAI ? (
                        <Button size="sm" variant="v2Button" isLoading={isUpdating} onClick={() => setAllowed(true)}>
                            {t('RESPONSES_STAFF.AI_ALLOW')}
                        </Button>
                    ) : (
                        <p className="text-xs text-black-600">{t('RESPONSES_STAFF.AI_ADMIN_CAN')}</p>
                    )}
                </div>
            ) : !insight ? (
                <div className="flex flex-col items-start gap-2.5">
                    <p className="max-w-[68ch] text-[13px] leading-relaxed text-black-600">
                        {t('RESPONSES_STAFF.AI_INTRO_1', { provider: providerName })} <span className="font-medium">{t('RESPONSES_STAFF.AI_ONLY_ON_CLICK')}</span>
                        {t('RESPONSES_STAFF.AI_INTRO_2')}
                        {allowedSince ? ` ${t('RESPONSES_STAFF.AI_SINCE', { date: when(allowedSince) })}` : ''}
                        {t('RESPONSES_STAFF.AI_INTRO_3', { provider: providerName })}
                    </p>
                    {error && <p className="text-xs text-[#7A2E2E]">{error}</p>}
                    <div className="flex flex-wrap items-center gap-3">
                        <Button size="sm" variant="v2Button" isLoading={isGenerating} disabled={!aiEnabled} onClick={handleGenerate}>
                            {t('RESPONSES_STAFF.AI_SUMMARIZE')}
                        </Button>
                        {canManageAI && (
                            <button type="button" disabled={isUpdating} onClick={() => setAllowed(false)} className="text-xs text-black-600 underline decoration-dotted underline-offset-2 hover:text-black-800">
                                {t('RESPONSES_STAFF.AI_STOP')}
                            </button>
                        )}
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
                            <span className="font-medium text-black-900">{t('RESPONSES_STAFF.AI_WORTH')}</span>{' '}
                            <span className="text-black-700">{insight.actionable.join(' · ')}</span>
                        </div>
                    )}
                    {insight.sentiment && <p className="text-xs text-black-600">{insight.sentiment}</p>}
                    {error && <p className="text-xs text-[#7A2E2E]">{error}</p>}
                    <p className="text-[10.5px] text-black-600">
                        {[
                            insight.responseCount === insight.totalResponses ? t('RESPONSES_STAFF.AI_BASED_ALL', { total: insight.totalResponses }) : t('RESPONSES_STAFF.AI_BASED_PART', { shown: insight.responseCount, total: insight.totalResponses }),
                            ...(insight.analysedSince ? [t('RESPONSES_STAFF.AI_BASED_SINCE', { date: when(insight.analysedSince) })] : [])
                        ].join(' ')}
                        {typeof insight.noticeShownResponses === 'number' && insight.noticeShownResponses < insight.totalResponses
                            ? ` · ${t('RESPONSES_STAFF.AI_WITHOUT_NOTICE', { missing: insight.totalResponses - insight.noticeShownResponses, total: insight.totalResponses })}`
                            : ''}
                        {` · ${t('RESPONSES_STAFF.AI_GENERATED', { date: when(insight.generatedAt) })} · ${t('RESPONSES_STAFF.AI_SENT_TO', { provider: providerName, sends })}`}
                    </p>
                </div>
            )}
        </div>
    );
}

/**
 * The AI summary as a bar of its own: a button in the row of the response
 * tabs, closed unless the page asks for it open. Nothing is asked of the server
 * (the cached summary, the workspace's AI settings) until it is opened, and the
 * summary opens full width under the row.
 */
export default function AIInsightsCard({ defaultOpen = false }: { defaultOpen?: boolean }) {
    const { t } = useTranslation();
    const [open, setOpen] = useState(defaultOpen);
    const panelId = `${useId()}-ai-summary`;
    return (
        <>
            <button
                type="button"
                aria-expanded={open}
                aria-controls={panelId}
                onClick={() => setOpen((value) => !value)}
                className="border-black-300 text-black-700 hover:bg-black-200 hover:text-black-900 focus-visible:ring-brand-500 ml-auto flex h-9 items-center gap-2 rounded border bg-white px-3 text-sm font-medium focus:outline-hidden focus-visible:ring-2"
            >
                <Sparkles className="text-brand-500 h-4 w-4" aria-hidden="true" />
                {t('RESPONSES_STAFF.AI_SUMMARY')}
                <ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
            </button>
            {open && (
                <div id={panelId} className="w-full basis-full">
                    <AIInsightsBody />
                </div>
            )}
        </>
    );
}
