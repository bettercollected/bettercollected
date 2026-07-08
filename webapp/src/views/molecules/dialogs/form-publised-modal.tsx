'use client';

import { useState } from 'react';

import { Check, Copy, ExternalLink } from 'lucide-react';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/form-utils';

/**
 * Post-publish moment, on the trust system and matching the Share modal's
 * idiom: one calm confirmation, the link front-and-centre with copy/open,
 * and honest next steps as quiet links — no double celebration, no dead-end
 * "go to dashboard" as the only exit.
 */
export default function FormPublishedModal(props: any) {
    const { toast } = useToast();
    const workspace = useAppSelector(selectWorkspace);
    const standardForm = useAppSelector(selectForm);
    const authState = useAppSelector(selectAuth);
    const [copied, setCopied] = useState(false);

    const shareUrl = getFormShareURL(standardForm, workspace);
    const settingsUrl = `${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN}/${workspace.workspaceName}/dashboard/forms/${standardForm.formId}?view=FormLinks`;
    const dashboardUrl = `${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN}/${workspace.workspaceName}/dashboard/forms`;

    const handleCopy = () => {
        navigator.clipboard.writeText(shareUrl);
        setCopied(true);
        toast({ description: 'Link copied to clipboard' });
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        {/* min-w-0 matters: DialogContent is display:grid, and a grid item's
            implicit min-width:auto lets the unbreakable URL dictate the width —
            overflowing the dialog instead of truncating. */}
        <div className="flex w-full min-w-0 max-w-full flex-col gap-6 overflow-hidden p-6 sm:p-8">
            <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-2.5">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#E7F4EE]">
                        <Check className="h-4 w-4 text-[#0E8A5F]" strokeWidth={3} />
                    </span>
                    <h2 className="text-black-900 text-lg font-semibold leading-snug">Your form is live</h2>
                </div>
                {/* Honest about what publishing means — same line the Share modal uses. */}
                <p className="text-black-600 text-sm leading-relaxed">Anyone with this link can open and respond to your form.</p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <div className="border-black-300 bg-black-100 flex min-w-0 flex-1 items-center gap-2 rounded-lg border px-3.5 py-3">
                    <span className="text-black-800 min-w-0 flex-1 truncate text-sm" title={shareUrl}>
                        {shareUrl}
                    </span>
                    <a
                        href={shareUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="Open form in a new tab"
                        data-umami-event={'PublishModal Open Form Link'}
                        data-umami-event-email={authState.email}
                        className="text-black-500 hover:text-brand-500 shrink-0 transition-colors"
                    >
                        <ExternalLink className="h-4 w-4" />
                    </a>
                </div>
                <Button
                    size="medium"
                    variant="primary"
                    onClick={handleCopy}
                    icon={copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    className="shrink-0"
                    data-umami-event={'PublishModal Copy Button'}
                    data-umami-event-email={authState.email}
                >
                    {copied ? 'Copied' : 'Copy link'}
                </Button>
            </div>

            <div className="border-t-black-200 flex flex-col gap-2.5 border-t pt-5">
                <span className="text-black-500 text-xs font-medium uppercase tracking-wide">Next steps</span>
                <div className="text-black-700 flex flex-col gap-2 text-sm">
                    <a href={settingsUrl} data-umami-event={'PublishModal Goto Settings Link'} data-umami-event-email={authState.email} className="hover:text-brand-600 text-brand-500 w-fit font-medium underline-offset-2 hover:underline">
                        Form settings — custom domain, privacy, integrations
                    </a>
                    <a href={dashboardUrl} data-umami-event={'PublishModal Goto Dashboard Link'} data-umami-event-email={authState.email} className="hover:text-brand-600 text-brand-500 w-fit font-medium underline-offset-2 hover:underline">
                        Back to dashboard
                    </a>
                </div>
            </div>
        </div>
    );
}
