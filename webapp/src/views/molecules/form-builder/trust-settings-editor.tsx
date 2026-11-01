'use client';

import { useEffect, useState } from 'react';

import { Shield } from 'lucide-react';
import { Trans } from 'react-i18next';
import { useTranslation } from 'react-i18next';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectForm, setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { httpUrl } from '@app/utils/http-url';
import { workspaceDisplayName } from '@app/utils/workspace-display-name';
import { MAX_RETENTION_DAYS, describeRetention, retentionDate, retentionDays } from '@app/utils/retention';

type RetentionKind = 'forever' | 'days' | 'date';

/**
 * Trust & privacy, authored where the form is built (DESIGN.md §4):
 * why the data is collected, how long it's kept, and where the policy lives.
 * Feeds the responder-facing trust strip on every step — the live preview
 * below shows exactly what responders will read.
 */
export default function TrustSettingsEditor() {
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const dispatch = useAppDispatch();
    const { toast } = useToast();
    const { t } = useTranslation('builder');
    const [patchFormSettings] = usePatchFormSettingsMutation();

    const [purpose, setPurpose] = useState(form?.settings?.purpose ?? '');
    const [privacyUrl, setPrivacyUrl] = useState(form?.settings?.privacyPolicyUrl ?? '');
    const [keepKind, setKeepKind] = useState<RetentionKind>((form?.settings?.responseExpirationType as RetentionKind) || 'forever');
    const [keepValue, setKeepValue] = useState(form?.settings?.responseExpiration ?? '');
    const [keepError, setKeepError] = useState('');
    const [privacyUrlError, setPrivacyUrlError] = useState('');
    const { t: tRespondent, language } = useRespondentLanguage();

    useEffect(() => {
        setPurpose(form?.settings?.purpose ?? '');
        setPrivacyUrl(form?.settings?.privacyPolicyUrl ?? '');
        setKeepKind((form?.settings?.responseExpirationType as RetentionKind) || 'forever');
        setKeepValue(form?.settings?.responseExpiration ?? '');
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [form?.formId]);

    const save = async (body: Record<string, string>) => {
        const response: any = await patchFormSettings({ workspaceId: workspace.id, formId: form.formId, body });
        if (response.data) {
            dispatch(setFormSettings(response.data.settings));
            return true;
        }
        toast({ description: t('TRUST.SAVE_FAILED'), variant: 'destructive' });
        return false;
    };

    // How long answers are kept: applied by the server to every new
    // submission, and stated to respondents in plain words.
    const saveRetention = async (kind: RetentionKind, value: string) => {
        setKeepError('');
        if (kind === 'days' && !retentionDays(value)) {
            setKeepError(t('TRUST.DAYS_ERROR', { max: MAX_RETENTION_DAYS }));
            return;
        }
        if (kind === 'date' && (!retentionDate(value) || value <= new Date().toISOString().slice(0, 10))) {
            setKeepError(t('TRUST.DATE_ERROR'));
            return;
        }
        await save(kind === 'forever' ? { responseExpirationType: 'forever' } : { responseExpirationType: kind, responseExpiration: value.trim() });
    };
    // The enforced period: the one statement responders read.
    const previewRetention = describeRetention({ ...(form?.settings as any), responseExpirationType: keepKind, responseExpiration: keepValue }, tRespondent, language, 'value');

    const inputClass = 'border-control focus:border-black-400 w-full rounded-lg border p-2 text-xs';

    return (
        <div className="flex flex-col gap-3 px-4 py-6">
            <div className="text-xs font-semibold uppercase tracking-wide text-black-600">{t('TRUST.TITLE')}</div>
            <div className="text-xs text-black-600">{t('TRUST.INTRO')}</div>

            <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-black-700">{t('TRUST.PURPOSE')}</span>
                <input type="text" placeholder={t('TRUST.PURPOSE_PLACEHOLDER')} value={purpose} onChange={(e) => setPurpose(e.target.value)} onBlur={() => save({ purpose: purpose.trim() })} className={inputClass} />
            </label>
            <div className="flex flex-col gap-1">
                <label htmlFor="keep-answers" className="text-xs font-medium text-black-700">
                    {t('TRUST.KEEP')}
                </label>
                <select
                    id="keep-answers"
                    value={keepKind}
                    onChange={(e) => {
                        const kind = e.target.value as RetentionKind;
                        setKeepKind(kind);
                        if (kind === 'forever') saveRetention(kind, '');
                    }}
                    className={inputClass}
                >
                    <option value="forever">{t('TRUST.KEEP_FOREVER')}</option>
                    <option value="days">{t('TRUST.KEEP_DAYS')}</option>
                    <option value="date">{t('TRUST.KEEP_DATE')}</option>
                </select>
                {keepKind === 'days' && (
                    <input
                        type="number"
                        min={1}
                        max={MAX_RETENTION_DAYS}
                        aria-label={t('TRUST.DAYS_LABEL')}
                        placeholder={t('TRUST.DAYS_PLACEHOLDER')}
                        value={keepValue}
                        onChange={(e) => setKeepValue(e.target.value)}
                        onBlur={() => saveRetention('days', keepValue)}
                        className={inputClass}
                    />
                )}
                {keepKind === 'date' && <input type="date" aria-label={t('TRUST.UNTIL_LABEL')} value={retentionDate(keepValue) ?? ''} onChange={(e) => setKeepValue(e.target.value)} onBlur={() => saveRetention('date', keepValue)} className={inputClass} />}
                {keepError ? (
                    <span role="alert" className="text-[11px] text-amber-700">
                        {keepError}
                    </span>
                ) : (
                    <span className="text-[11px] text-black-600">{keepKind === 'forever' ? t('TRUST.KEEP_HINT_FOREVER') : t('TRUST.KEEP_HINT_LIMITED')}</span>
                )}
            </div>
            <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-black-700">{t('TRUST.POLICY_LINK')}</span>
                <input
                    type="url"
                    placeholder="https://…"
                    value={privacyUrl}
                    onChange={(e) => setPrivacyUrl(e.target.value)}
                    onBlur={() => {
                        // Respondents get it as a link: http(s) only.
                        if (privacyUrl.trim() && !httpUrl(privacyUrl)) {
                            setPrivacyUrlError(t('TRUST.POLICY_ERROR'));
                            return;
                        }
                        setPrivacyUrlError('');
                        save({ privacyPolicyUrl: privacyUrl.trim() });
                    }}
                    className={inputClass}
                />
                {privacyUrlError && (
                    <span role="alert" className="text-[11px] text-amber-700">
                        {privacyUrlError}
                    </span>
                )}
            </label>

            {/* Live preview of the responder-facing trust strip. */}
            <div className="mt-1 flex flex-col gap-1">
                <span className="text-[10px] font-medium uppercase tracking-wide text-black-600">{t('TRUST.PREVIEW_TITLE')}</span>
                <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 rounded border border-black-300 bg-white px-2.5 py-2 text-[11px] text-black-700">
                    <Shield className="h-3 w-3 shrink-0 text-brand-500" strokeWidth={1.8} aria-hidden="true" />
                    <span>
                        <Trans t={tRespondent} i18nKey="PRIVACY.COLLECTED_BY" values={{ owner: workspaceDisplayName(workspace) ?? tRespondent('PRIVACY.OWNER_FALLBACK') }} components={{ 1: <span className="font-semibold text-black-900" /> }} />
                    </span>
                    {purpose.trim() && <span>· {purpose.trim()}</span>}
                    {httpUrl(privacyUrl) && <span className="text-brand-500">· {t('TRUST.PREVIEW_POLICY')}</span>}
                    <span>· {previewRetention}</span>
                    <span>· {tRespondent('PRIVACY.RIGHTS_TEXT')}</span>
                </div>
            </div>
        </div>
    );
}
