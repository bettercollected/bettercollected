'use client';

import { useEffect, useState } from 'react';

import { Shield } from 'lucide-react';

import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectForm, setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

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

    useEffect(() => {
        setPurpose(form?.settings?.purpose ?? '');
        setRetention(form?.settings?.retentionText ?? '');
        setPrivacyUrl(form?.settings?.privacyPolicyUrl ?? '');
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [form?.formId]);

    const save = async (body: Record<string, string>) => {
        const response: any = await patchFormSettings({ workspaceId: workspace.id, formId: form.formId, body });
        if (response.data) {
            dispatch(setFormSettings(response.data.settings));
        } else {
            toast({ description: "Couldn't save trust settings.", variant: 'destructive' });
        }
    };

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
                <span className="text-black-700 text-xs font-medium">Retention</span>
                <input type="text" placeholder="e.g. kept for 90 days" value={retention} onChange={(e) => setRetention(e.target.value)} onBlur={() => save({ retentionText: retention.trim() })} className={inputClass} />
            </label>
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
                    <span>· View or delete your response anytime{retention.trim() ? ` · ${retention.trim()}` : ''}</span>
                </div>
            </div>
        </div>
    );
}
