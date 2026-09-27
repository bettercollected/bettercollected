'use client';

import React from 'react';

import Link from 'next/link';

import { Sparkles } from 'lucide-react';

import { Button } from '@app/shadcn/components/ui/button';
import { useAppSelector } from '@app/store/hooks';
import { WorkspaceAISettings, useGetAISettingsQuery, useUpdateAISettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/**
 * Workspace AI consent in the UI (#715). The server refuses every AI call
 * until a workspace admin has opted in (403 `ai_not_enabled`); these pieces
 * make that visible where AI is offered: the opt-in in context, and a
 * disclosure naming the provider and what is sent.
 */

export const aiSettingsUrl = (workspaceName?: string) => `/${workspaceName ?? ''}/dashboard/ai-settings`;

export function useWorkspaceAI() {
    const workspace = useAppSelector(selectWorkspace);
    const { data, isLoading, refetch } = useGetAISettingsQuery(workspace?.id, { skip: !workspace?.id });
    const settings = data as WorkspaceAISettings | undefined;
    return {
        workspace,
        settings,
        isLoading,
        refetch,
        enabled: !!settings?.enabled,
        providerName: settings?.providerName ?? settings?.defaultProviderName ?? 'the AI provider'
    };
}

/** True when an API error is the server's "AI is off for this workspace". */
export function isAINotEnabledError(error: any): boolean {
    return error?.status === 403 && error?.data?.code === 'ai_not_enabled';
}

/** Error text for an AI request: the server's message, whatever its shape. */
export function aiErrorMessage(error: any, fallback: string): string {
    const detail = error?.data;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail.message === 'string') return detail.message;
    return fallback;
}

interface DisclosureProps {
    /** What this feature sends, e.g. "this form's questions and settings". */
    sends: string;
    className?: string;
}

/** One line under an AI action: who receives what, and where to change it. */
export function AIDisclosure({ sends, className }: DisclosureProps) {
    const { workspace, providerName } = useWorkspaceAI();
    return (
        <p className={className ?? 'text-[10.5px] leading-relaxed text-black-500'}>
            Sent to {providerName}: {sends}.{' '}
            <Link href={aiSettingsUrl(workspace?.workspaceName)} className="underline decoration-dotted underline-offset-2">
                AI settings
            </Link>
        </p>
    );
}

interface OptInProps {
    /** The feature asking, e.g. "The form assistant". */
    feature: string;
    /** What it would send once AI is on. */
    sends: string;
    /** Called after an admin turned AI on here. */
    onEnabled?: () => void;
    compact?: boolean;
}

/**
 * Shown instead of an AI feature while the workspace has not opted in: an
 * admin can turn AI on right here (for the instance's default provider, named),
 * anyone else is told who can.
 */
export function AIOptIn({ feature, sends, onEnabled, compact }: OptInProps) {
    const { workspace, settings } = useWorkspaceAI();
    const [update, { isLoading }] = useUpdateAISettingsMutation();
    const [error, setError] = React.useState<string | null>(null);
    const providerName = settings?.defaultProviderName ?? 'the AI provider';
    const configured = settings?.providers?.find((p) => p.id === settings?.defaultProvider)?.configured ?? false;

    const turnOn = async () => {
        setError(null);
        const response: any = await update({ workspace_id: workspace.id, body: { enabled: true } });
        if (response.data?.enabled) onEnabled?.();
        else setError(aiErrorMessage(response.error, 'Could not turn AI on. Please try again.'));
    };

    return (
        <div className={`flex flex-col gap-2 rounded-lg border border-black-200 bg-white ${compact ? 'p-3' : 'p-4'}`} role="region" aria-label="AI is off for this workspace">
            <div className="flex items-center gap-1.5 text-[13px] font-semibold text-black-900">
                <Sparkles className="h-3.5 w-3.5 text-brand-500" />
                AI is off for this workspace
            </div>
            <p className="text-xs leading-relaxed text-black-600">
                {feature} uses an external AI provider. Nothing is sent to one until a workspace admin turns AI on. Once on, it sends {sends} to {providerName}.
            </p>
            {!settings ? null : !configured ? (
                <p className="text-xs text-black-500">No AI provider is set up on this server.</p>
            ) : settings.canManage ? (
                <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" variant="v2Button" isLoading={isLoading} onClick={turnOn}>
                        Turn on AI with {providerName}
                    </Button>
                    <Link href={aiSettingsUrl(workspace?.workspaceName)} className="text-xs text-black-600 underline decoration-dotted underline-offset-2">
                        AI settings
                    </Link>
                </div>
            ) : (
                <p className="text-xs text-black-500">
                    Ask a workspace admin to turn it on in{' '}
                    <Link href={aiSettingsUrl(workspace?.workspaceName)} className="underline decoration-dotted underline-offset-2">
                        AI settings
                    </Link>
                    .
                </p>
            )}
            {error && <p className="text-xs text-[#7A2E2E]">{error}</p>}
        </div>
    );
}
