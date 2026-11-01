'use client';

import { useEffect, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';

import { aiErrorMessage } from '@app/components/ai/ai-consent';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { WorkspaceAISettings, useGetAISettingsQuery, useUpdateAIMemorySettingsMutation, useUpdateAISettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

// What each AI feature sends once AI is on (mirrors the backend's AI paths).
const WHAT_IS_SENT: Array<{ feature: string; sends: string }> = [
    { feature: 'STAFF.AI_SETTINGS.FEATURE_CHAT', sends: 'STAFF.AI_SETTINGS.SENDS_CHAT' },
    { feature: 'STAFF.AI_SETTINGS.FEATURE_REVIEW', sends: 'STAFF.AI_SETTINGS.SENDS_REVIEW' },
    { feature: 'STAFF.AI_SETTINGS.FEATURE_START', sends: 'STAFF.AI_SETTINGS.SENDS_START' },
    { feature: 'STAFF.AI_SETTINGS.FEATURE_PDF', sends: 'STAFF.AI_SETTINGS.SENDS_PDF' },
    { feature: 'STAFF.AI_SETTINGS.FEATURE_LEARN', sends: 'STAFF.AI_SETTINGS.SENDS_LEARN' }
];

/**
 * Workspace AI settings (#715): the admin's opt-in for every AI feature in
 * this workspace, for one named provider, and each member's own "Learn my
 * preferences" setting. Off by default; nothing is sent to an AI provider
 * while it is off.
 */
export default function AISettingsPage() {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const { toast } = useToast();
    const { data, isLoading } = useGetAISettingsQuery(workspace?.id, { skip: !workspace?.id });
    const settings = data as WorkspaceAISettings | undefined;
    const [update, { isLoading: isSaving }] = useUpdateAISettingsMutation();
    const [updateLearning, { isLoading: isSavingLearning }] = useUpdateAIMemorySettingsMutation();
    const [provider, setProvider] = useState<string>('');

    const configured = (settings?.providers ?? []).filter((p) => p.configured);
    useEffect(() => {
        if (!settings || provider) return;
        const preferred = configured.find((p) => p.id === settings.defaultProvider) ?? configured[0];
        if (preferred) setProvider(preferred.id);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [settings]);
    const chosenName = configured.find((p) => p.id === provider)?.name ?? settings?.defaultProviderName ?? t('STAFF.AI.DEFAULT_PROVIDER');

    const setEnabled = async (enabled: boolean) => {
        const response: any = await update({ workspace_id: workspace.id, body: enabled ? { enabled, provider } : { enabled } });
        if (response.data) toast({ description: enabled ? t('STAFF.AI_SETTINGS.IS_ON', { provider: response.data.providerName }) : t('STAFF.AI_SETTINGS.IS_OFF') });
        else toast({ description: aiErrorMessage(response.error, t('STAFF.AI_SETTINGS.SAVE_FAILED')), variant: 'destructive' });
    };

    const setLearning = async (learnPreferences: boolean) => {
        const response: any = await updateLearning({ workspace_id: workspace.id, body: { learnPreferences } });
        if (!response.data) toast({ description: t('STAFF.AI_SETTINGS.SAVE_FAILED'), variant: 'destructive' });
    };

    if (isLoading || !settings) {
        return <div className="pb-10 text-sm text-black-600">{t('STAFF.COMMON.LOADING')}</div>;
    }

    return (
        <div className="flex w-full max-w-[760px] flex-col gap-8 pb-10">
            <div className="flex flex-col gap-2">
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-600">
                    {t('STAFF.AI_SETTINGS.INTRO')}
                </p>
            </div>

            <section className="flex flex-col gap-3 rounded-lg border border-black-400 p-4" aria-labelledby="ai-workspace-heading">
                <h2 id="ai-workspace-heading" className="text-sm font-semibold text-black-900">
                    {t('STAFF.AI_SETTINGS.WORKSPACE_TITLE')}
                </h2>
                {settings.enabled ? (
                    <p className="text-sm text-black-700">
                        <Trans i18nKey="STAFF.AI_SETTINGS.ON_WITH" values={{ provider: settings.providerName }} components={{ 1: <span className="font-medium" /> }} />
                        {settings.enabledAt && (
                            <span className="text-black-600">
                                {' '}
                                · {t(settings.enabledBy === auth?.id ? 'STAFF.AI_SETTINGS.TURNED_ON_BY_YOU' : 'STAFF.AI_SETTINGS.TURNED_ON_BY_ADMIN', { date: new Date(settings.enabledAt).toLocaleString(locale) })}
                            </span>
                        )}
                    </p>
                ) : (
                    <p className="text-sm text-black-700">{t('STAFF.AI_SETTINGS.OFF')}</p>
                )}

                <div className="flex flex-col gap-1.5">
                    <p className="text-xs font-medium text-black-600">{t('STAFF.AI_SETTINGS.WHAT_IS_SENT')}</p>
                    <ul className="flex flex-col gap-1">
                        {WHAT_IS_SENT.map((item) => (
                            <li key={item.feature} className="text-xs leading-relaxed text-black-600">
                                <span className="font-medium text-black-800">{t(item.feature)}:</span> {t(item.sends)}.
                            </li>
                        ))}
                    </ul>
                </div>

                {settings.canManage ? (
                    settings.enabled ? (
                        <div>
                            <Button size="sm" variant="v2Button" isLoading={isSaving} onClick={() => setEnabled(false)}>
                                {t('STAFF.AI_SETTINGS.TURN_OFF')}
                            </Button>
                        </div>
                    ) : configured.length === 0 ? (
                        <p className="text-xs text-black-600">{t('STAFF.AI_SETTINGS.NO_PROVIDER')}</p>
                    ) : (
                        <div className="flex flex-wrap items-center gap-2">
                            {configured.length > 1 && (
                                <select aria-label={t('STAFF.AI_SETTINGS.PROVIDER')} value={provider} onChange={(e) => setProvider(e.target.value)} className="h-8 rounded-md border border-black-300 bg-white px-2 text-sm">
                                    {configured.map((p) => (
                                        <option key={p.id} value={p.id}>
                                            {p.name}
                                        </option>
                                    ))}
                                </select>
                            )}
                            <Button size="sm" variant="primary" isLoading={isSaving} disabled={!provider} onClick={() => setEnabled(true)}>
                                {t('STAFF.AI_SETTINGS.TURN_ON', { provider: chosenName })}
                            </Button>
                        </div>
                    )
                ) : (
                    <p className="text-xs text-black-600">{t('STAFF.COMMON.ONLY_ADMINS')}</p>
                )}
            </section>

            <section className="flex flex-col gap-2 rounded-lg border border-black-400 p-4" aria-labelledby="ai-learning-heading">
                <h2 id="ai-learning-heading" className="text-sm font-semibold text-black-900">
                    {t('STAFF.AI_SETTINGS.LEARN_TITLE')}
                </h2>
                <p className="text-xs leading-relaxed text-black-600">
                    {t('STAFF.AI_SETTINGS.LEARN_BODY')}
                </p>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-black-800">
                    <input type="checkbox" checked={settings.learnPreferences} disabled={isSavingLearning} onChange={(e) => setLearning(e.target.checked)} className="h-4 w-4" />
                    {t('STAFF.AI_SETTINGS.LEARN_CHECK')}
                </label>
            </section>
        </div>
    );
}
