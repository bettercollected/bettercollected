'use client';

import { useState } from 'react';

import Link from 'next/link';

import { Check, Copy } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { useGetEmbedSettingsQuery } from '@app/store/workspaces/embed-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { embedSnippet, iframeSnippet } from '@app/utils/form-embed';

/**
 * The share dialog's Embed tab (docs/embed.md): the code to paste, and which sites the workspace allows to
 * show the form (a site that is not listed is refused by the browser).
 */
export default function EmbedPanel({ url, formTitle }: { url: string; formTitle?: string }) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [, copyToClipboard] = useCopyToClipboard();
    const [copied, setCopied] = useState<'script' | 'frame' | null>(null);
    const workspace = useAppSelector(selectWorkspace);
    const { can } = useWorkspacePermissions();
    const settings = useGetEmbedSettingsQuery(workspace?.id as string, { skip: !workspace?.id });
    const snippet = embedSnippet(url, formTitle);
    const frame = iframeSnippet(url, formTitle);
    const origins = settings.data?.origins ?? [];
    const manageUrl = `/${workspace?.workspaceName}/dashboard/embedding`;

    const copy = (which: 'script' | 'frame') => {
        copyToClipboard(which === 'script' ? snippet : frame);
        setCopied(which);
        toast({ description: t('STAFF.EMBED.COPIED_TOAST') });
        setTimeout(() => setCopied(null), 2000);
    };

    return (
        <div className="flex min-w-0 flex-col gap-5">
            <p className="text-sm leading-relaxed text-black-600">{t('STAFF.EMBED.INTRO')}</p>

            <CodeBlock
                id="embed-snippet-label"
                label={t('STAFF.EMBED.SNIPPET_LABEL')}
                code={snippet}
                copyLabel={copied === 'script' ? t('STAFF.EMBED.COPIED') : t('STAFF.EMBED.COPY')}
                copied={copied === 'script'}
                onCopy={() => copy('script')}
                hint={t('STAFF.EMBED.TITLE_HINT')}
            />

            <CodeBlock
                id="embed-frame-label"
                label={t('STAFF.EMBED.IFRAME_LABEL')}
                code={frame}
                copyLabel={copied === 'frame' ? t('STAFF.EMBED.COPIED') : t('STAFF.EMBED.IFRAME_COPY')}
                copied={copied === 'frame'}
                onCopy={() => copy('frame')}
                hint={t('STAFF.EMBED.IFRAME_HINT')}
            />

            <div className="flex flex-col gap-2 border-t border-t-black-300 pt-4">
                <span className="text-sm font-semibold text-black-900">{t('STAFF.EMBED.SITES_TITLE')}</span>
                {settings.isLoading ? (
                    <p className="text-sm text-black-600" role="status">
                        {t('STAFF.EMBED.SITES_LOADING')}
                    </p>
                ) : origins.length === 0 ? (
                    <p className="text-sm text-black-700">{t('STAFF.EMBED.SITES_NONE')}</p>
                ) : (
                    <ul className="flex flex-wrap gap-1.5">
                        {origins.map((origin) => (
                            <li key={origin} className="rounded border border-black-300 bg-white px-2 py-1 font-mono text-[12px] text-black-800">
                                {origin}
                            </li>
                        ))}
                    </ul>
                )}
                {!settings.isLoading &&
                    (can(WorkspacePermission.WORKSPACE_MANAGE) ? (
                        <Link href={manageUrl} className="w-fit text-sm font-medium text-brand-600 underline underline-offset-2 hover:text-brand-700">
                            {origins.length === 0 ? t('STAFF.EMBED.SITES_ADD') : t('STAFF.EMBED.SITES_MANAGE')}
                        </Link>
                    ) : (
                        origins.length === 0 && <p className="text-sm text-black-600">{t('STAFF.EMBED.SITES_ASK_ADMIN')}</p>
                    ))}
            </div>

            <p className="text-xs leading-relaxed text-black-600">{t('STAFF.EMBED.SIGN_IN_NOTE')}</p>
        </div>
    );
}

function CodeBlock({ id, label, code, copyLabel, copied, onCopy, hint }: { id: string; label: string; code: string; copyLabel: string; copied: boolean; onCopy: () => void; hint: string }) {
    return (
        <div className="flex min-w-0 flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
                <span id={id} className="text-xs font-medium tracking-wide text-black-600 uppercase">
                    {label}
                </span>
                <Button size="sm" variant="primary" onClick={onCopy} icon={copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />} className="shrink-0">
                    {copyLabel}
                </Button>
            </div>
            {/* focusable so that a keyboard user can scroll a long line (WCAG 2.1.1) */}
            {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
            <pre tabIndex={0} aria-labelledby={id} className="max-w-full overflow-x-auto rounded-lg border border-black-300 bg-black-100 px-3.5 py-3 font-mono text-[12px] leading-relaxed break-all whitespace-pre-wrap text-black-800">
                {code}
            </pre>
            <p className="text-xs text-black-600">{hint}</p>
        </div>
    );
}
