'use client';

import { useEffect, useState } from 'react';

import { aiErrorMessage } from '@app/components/ai/ai-consent';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { WorkspaceAISettings, useGetAISettingsQuery, useUpdateAIMemorySettingsMutation, useUpdateAISettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

// What each AI feature sends once AI is on (mirrors the backend's AI paths).
const WHAT_IS_SENT: Array<{ feature: string; sends: string }> = [
    { feature: 'Form assistant (chat)', sends: "the form's questions and settings, your messages, the workspace AI profile and your AI memory" },
    { feature: 'Compliance review', sends: "the form's questions and settings and the workspace AI profile" },
    { feature: 'Start with AI', sends: 'your prompt, the workspace AI profile and your AI memory' },
    { feature: 'PDF import', sends: 'the page text and page images of the uploaded file, only when the uploader also agrees for that file' },
    { feature: 'Learn my preferences', sends: "your chat message and the assistant's reply, only when you turn it on below" }
];

/**
 * Workspace AI settings (#715): the admin's opt-in for every AI feature in
 * this workspace, for one named provider, and each member's own "Learn my
 * preferences" setting. Off by default; nothing is sent to an AI provider
 * while it is off.
 */
export default function AISettingsPage() {
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
    const chosenName = configured.find((p) => p.id === provider)?.name ?? settings?.defaultProviderName ?? 'the AI provider';

    const setEnabled = async (enabled: boolean) => {
        const response: any = await update({ workspace_id: workspace.id, body: enabled ? { enabled, provider } : { enabled } });
        if (response.data) toast({ description: enabled ? `AI is on, with ${response.data.providerName}` : 'AI is off for this workspace' });
        else toast({ description: aiErrorMessage(response.error, 'Could not save. Please try again.'), variant: 'destructive' });
    };

    const setLearning = async (learnPreferences: boolean) => {
        const response: any = await updateLearning({ workspace_id: workspace.id, body: { learnPreferences } });
        if (!response.data) toast({ description: 'Could not save. Please try again.', variant: 'destructive' });
    };

    if (isLoading || !settings) {
        return <div className="px-5 py-6 text-sm text-black-500 lg:px-10">Loading…</div>;
    }

    return (
        <div className="flex w-full max-w-[760px] flex-col gap-8 px-5 py-6 lg:px-10">
            <div className="flex flex-col gap-2">
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-600">
                    AI features send content from this workspace to an external AI provider. They stay off until a workspace admin turns them on here, and they only ever use the provider named below.
                </p>
            </div>

            <section className="flex flex-col gap-3 rounded-lg border border-black-200 p-4" aria-labelledby="ai-workspace-heading">
                <h2 id="ai-workspace-heading" className="text-sm font-semibold text-black-900">
                    AI features for this workspace
                </h2>
                {settings.enabled ? (
                    <p className="text-sm text-black-700">
                        On, with <span className="font-medium">{settings.providerName}</span>
                        {settings.enabledAt && (
                            <span className="text-black-500">
                                {' '}
                                · turned on {settings.enabledBy === auth?.id ? 'by you' : 'by a workspace admin'} on {new Date(settings.enabledAt).toLocaleString()}
                            </span>
                        )}
                    </p>
                ) : (
                    <p className="text-sm text-black-700">Off. Nothing from this workspace is sent to an AI provider.</p>
                )}

                <div className="flex flex-col gap-1.5">
                    <p className="text-xs font-medium text-black-600">What is sent, and when</p>
                    <ul className="flex flex-col gap-1">
                        {WHAT_IS_SENT.map((item) => (
                            <li key={item.feature} className="text-xs leading-relaxed text-black-600">
                                <span className="font-medium text-black-800">{item.feature}:</span> {item.sends}.
                            </li>
                        ))}
                    </ul>
                </div>

                {settings.canManage ? (
                    settings.enabled ? (
                        <div>
                            <Button size="sm" variant="v2Button" isLoading={isSaving} onClick={() => setEnabled(false)}>
                                Turn AI off
                            </Button>
                        </div>
                    ) : configured.length === 0 ? (
                        <p className="text-xs text-black-500">No AI provider is set up on this server.</p>
                    ) : (
                        <div className="flex flex-wrap items-center gap-2">
                            {configured.length > 1 && (
                                <select aria-label="AI provider" value={provider} onChange={(e) => setProvider(e.target.value)} className="h-8 rounded-md border border-black-300 bg-white px-2 text-sm">
                                    {configured.map((p) => (
                                        <option key={p.id} value={p.id}>
                                            {p.name}
                                        </option>
                                    ))}
                                </select>
                            )}
                            <Button size="sm" variant="primary" isLoading={isSaving} disabled={!provider} onClick={() => setEnabled(true)}>
                                Turn on AI with {chosenName}
                            </Button>
                        </div>
                    )
                ) : (
                    <p className="text-xs text-black-500">Only workspace admins can change this.</p>
                )}
            </section>

            <section className="flex flex-col gap-2 rounded-lg border border-black-200 p-4" aria-labelledby="ai-learning-heading">
                <h2 id="ai-learning-heading" className="text-sm font-semibold text-black-900">
                    Learn my preferences
                </h2>
                <p className="text-xs leading-relaxed text-black-600">
                    When on, after each form assistant turn your message and the assistant&apos;s reply are sent to the AI provider once more, to note lasting style preferences in your AI memory. Off by default; it only applies to you, and only while AI is
                    on for the workspace.
                </p>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-black-800">
                    <input type="checkbox" checked={settings.learnPreferences} disabled={isSavingLearning} onChange={(e) => setLearning(e.target.checked)} className="h-4 w-4" />
                    Learn my preferences from my chats
                </label>
            </section>
        </div>
    );
}
