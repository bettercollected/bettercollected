'use client';

import { useEffect, useState } from 'react';

import { Shield } from 'lucide-react';

import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectForm, setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { describeRetention, MAX_RETENTION_DAYS, retentionDate, retentionDays } from '@app/utils/retention';

type RetentionKind = 'forever' | 'days' | 'date';

/**
 * Trust & privacy, authored where the form is built (Design-Language §4):
 * why the data is collected, how long it's kept, and where the policy lives.
 * Feeds the responder-facing trust strip on every step — the live preview
 * below shows exactly what responders will read.
 */
export default function TrustSettingsEditor() {
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const dispatch = useAppDispatch();
    const { toast } = useToast();
    const [patchFormSettings] = usePatchFormSettingsMutation();

    const [purpose, setPurpose] = useState(form?.settings?.purpose ?? '');
    const [retention, setRetention] = useState(form?.settings?.retentionText ?? '');
    const [privacyUrl, setPrivacyUrl] = useState(form?.settings?.privacyPolicyUrl ?? '');
    const [keepKind, setKeepKind] = useState<RetentionKind>((form?.settings?.responseExpirationType as RetentionKind) || 'forever');
    const [keepValue, setKeepValue] = useState(form?.settings?.responseExpiration ?? '');
    const [keepError, setKeepError] = useState('');
    const { t: tRespondent, language } = useRespondentLanguage();

    useEffect(() => {
        setPurpose(form?.settings?.purpose ?? '');
        setRetention(form?.settings?.retentionText ?? '');
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
        toast({ description: "Couldn't save trust settings.", variant: 'destructive' });
        return false;
    };

    // How long answers are kept: applied by the server to every new
    // submission, and stated to respondents in plain words.
    const saveRetention = async (kind: RetentionKind, value: string) => {
        setKeepError('');
        if (kind === 'days' && !retentionDays(value)) {
            setKeepError(`Enter a number of days from 1 to ${MAX_RETENTION_DAYS}.`);
            return;
        }
        if (kind === 'date' && (!retentionDate(value) || value <= new Date().toISOString().slice(0, 10))) {
            setKeepError('Choose a date in the future.');
            return;
        }
        await save(kind === 'forever' ? { responseExpirationType: 'forever' } : { responseExpirationType: kind, responseExpiration: value.trim() });
    };
    const previewRetention = describeRetention({ ...(form?.settings as any), retentionText: retention, responseExpirationType: keepKind, responseExpiration: keepValue }, tRespondent, language);

    const inputClass = 'border-black-300 focus:border-black-400 w-full rounded-lg border p-2 text-xs';

    return (
        <div className="flex flex-col gap-3 px-4 py-6">
            <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Trust &amp; privacy</div>
            <div className="text-black-500 text-xs">Shown to responders on every step. Plain words build trust — say why you&apos;re asking and how long you keep answers.</div>

            <label className="flex flex-col gap-1">
                <span className="text-black-700 text-xs font-medium">Purpose</span>
                <input type="text" placeholder="e.g. To schedule your appointment" value={purpose} onChange={(e) => setPurpose(e.target.value)} onBlur={() => save({ purpose: purpose.trim() })} className={inputClass} />
            </label>
            <label className="flex flex-col gap-1">
                <span className="text-black-700 text-xs font-medium">Retention in your own words (optional)</span>
                <input type="text" placeholder="Shown instead of the period below" value={retention} onChange={(e) => setRetention(e.target.value)} onBlur={() => save({ retentionText: retention.trim() })} className={inputClass} />
            </label>
            <div className="flex flex-col gap-1">
                <label htmlFor="keep-answers" className="text-black-700 text-xs font-medium">
                    Keep answers
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
                    <option value="forever">Until they are deleted</option>
                    <option value="days">For a number of days</option>
                    <option value="date">Until a date</option>
                </select>
                {keepKind === 'days' && <input type="number" min={1} max={MAX_RETENTION_DAYS} aria-label="Days to keep answers" placeholder="e.g. 90" value={keepValue} onChange={(e) => setKeepValue(e.target.value)} onBlur={() => saveRetention('days', keepValue)} className={inputClass} />}
                {keepKind === 'date' && <input type="date" aria-label="Keep answers until" value={retentionDate(keepValue) ?? ''} onChange={(e) => setKeepValue(e.target.value)} onBlur={() => saveRetention('date', keepValue)} className={inputClass} />}
                {keepError ? (
                    <span role="alert" className="text-[11px] text-amber-700">
                        {keepError}
                    </span>
                ) : (
                    <span className="text-black-500 text-[11px]">{keepKind === 'forever' ? 'Answers are kept until they are deleted.' : 'Answers are deleted automatically after this. Applies to answers submitted from now on.'}</span>
                )}
            </div>
            <label className="flex flex-col gap-1">
                <span className="text-black-700 text-xs font-medium">Privacy policy link</span>
                <input type="url" placeholder="https://…" value={privacyUrl} onChange={(e) => setPrivacyUrl(e.target.value)} onBlur={() => save({ privacyPolicyUrl: privacyUrl.trim() })} className={inputClass} />
            </label>

            {/* Live preview of the responder-facing trust strip. */}
            <div className="mt-1 flex flex-col gap-1">
                <span className="text-black-500 text-[10px] font-medium uppercase tracking-wide">Responders will see</span>
                <div className="border-black-200 text-black-700 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 rounded-lg border bg-white px-2.5 py-2 text-[11px]">
                    <Shield className="h-3 w-3 shrink-0 text-[#2456CC]" strokeWidth={1.8} aria-hidden="true" />
                    <span>
                        Collected by <span className="text-black-900 font-semibold">{workspace?.title || workspace?.workspaceName}</span>
                    </span>
                    {purpose.trim() && <span>· {purpose.trim()}</span>}
                    {privacyUrl.trim() && <span className="text-[#2456CC]">· How your data is used</span>}
                    <span>· {previewRetention}</span>
                    <span>· You can view your answers and ask for them to be deleted at any time.</span>
                </div>
            </div>
        </div>
    );
}
