'use client';

import { ReactNode, useState } from 'react';

import cn from 'classnames';
import { Check, Copy, ExternalLink } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { FacebookShareButton, LinkedinShareButton, XShareButton } from 'react-share';

import { Facebook } from '@app/components/icons/brands/facebook';
import { Linkedin } from '@app/components/icons/brands/linkedin';
import { Twitter } from '@app/components/icons/brands/twitter';
import EmbedPanel from '@app/components/embed/embed-panel';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@app/shadcn/components/ui/tabs';
import { useToast } from '@app/shadcn/components/ui/use-toast';

type SizeNames = 'large' | 'small';

interface Props {
    url: string;
    title?: string;
    /** The form's title: the accessible name of the frame in the Embed tab's code. */
    formTitle?: string;
    showCopy?: boolean;
    iconSize?: SizeNames;
    className?: string;
}

// The share button carries the accessible name; this is only its visual face.
const SocialButton = ({ children }: { children: ReactNode }) => (
    <span
        aria-hidden="true"
        className="border-black-300 text-black-700 hover:border-brand-300 hover:bg-brand-100 flex h-10 w-10 items-center justify-center rounded-full border bg-white transition-colors"
    >
        {children}
    </span>
);

export default function ShareView({ url, title, formTitle, showCopy = true, className }: Props) {
    const { t } = useTranslation();
    const [, copyToClipboard] = useCopyToClipboard();
    const { toast } = useToast();
    const [copied, setCopied] = useState(false);
    // The Embed tab (docs/embed.md) while this server has embedding on, for members who may share forms.
    const { can, formEmbedEnabled } = useWorkspacePermissions();
    const embeddable = formEmbedEnabled && can(WorkspacePermission.FORM_SHARE);

    const handleCopy = () => {
        copyToClipboard(url);
        setCopied(true);
        toast({ description: t('STAFF.SHARE.COPIED_TOAST') });
        setTimeout(() => setCopied(false), 2000);
    };

    const heading = (
        <div className="flex flex-col gap-1.5">
            <h2 className="text-black-900 text-lg font-semibold leading-snug">{title || t('STAFF.SHARE.TITLE')}</h2>
            {/* Honest about what the link does — no coercion, no surprises. */}
            <p className="text-black-600 text-sm leading-relaxed">{t('STAFF.SHARE.INTRO')}</p>
        </div>
    );

    const linkPanel = (
        <>
            {showCopy && (
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <div className="border-black-300 bg-black-100 flex min-w-0 flex-1 items-center gap-2 rounded-lg border px-3.5 py-3">
                        <span className="text-black-800 min-w-0 flex-1 truncate font-mono text-[13px]" title={url}>
                            {url}
                        </span>
                        <a href={url} target="_blank" rel="noopener noreferrer" aria-label={t('STAFF.SHARE.OPEN_NEW_TAB')} className="text-black-600 hover:text-brand-500 shrink-0 transition-colors">
                            <ExternalLink className="h-4 w-4" />
                        </a>
                    </div>
                    <Button size="medium" variant="primary" onClick={handleCopy} icon={copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />} className="shrink-0">
                        {copied ? t('STAFF.SHARE.COPIED') : t('STAFF.SHARE.COPY')}
                    </Button>
                </div>
            )}

            <div className="flex flex-col gap-2.5">
                <span className="text-black-600 text-xs font-medium uppercase tracking-wide">{t('STAFF.SHARE.OR_SHARE_ON')}</span>
                <div className="flex items-center gap-3">
                    <XShareButton url={url} aria-label={t('STAFF.SHARE.ON_X')}>
                        <SocialButton>
                            <Twitter className="h-[18px] w-[18px]" />
                        </SocialButton>
                    </XShareButton>
                    <FacebookShareButton url={url} aria-label={t('STAFF.SHARE.ON_FACEBOOK')}>
                        <SocialButton>
                            <Facebook className="h-[18px] w-[18px]" />
                        </SocialButton>
                    </FacebookShareButton>
                    <LinkedinShareButton url={url} aria-label={t('STAFF.SHARE.ON_LINKEDIN')}>
                        <SocialButton>
                            <Linkedin className="h-[18px] w-[18px]" />
                        </SocialButton>
                    </LinkedinShareButton>
                </div>
            </div>
        </>
    );

    if (!embeddable) {
        return (
            <div className={cn('flex flex-col gap-6', className)}>
                {heading}
                {linkPanel}
            </div>
        );
    }

    return (
        <div className={cn('flex flex-col gap-6', className)}>
            {heading}
            <Tabs defaultValue="link" className="flex min-w-0 flex-col gap-4">
                <TabsList aria-label={t('STAFF.EMBED.TABS_LABEL')} className="w-fit">
                    <TabsTrigger value="link">{t('STAFF.EMBED.TAB_LINK')}</TabsTrigger>
                    <TabsTrigger value="embed">{t('STAFF.EMBED.TAB_EMBED')}</TabsTrigger>
                </TabsList>
                <TabsContent value="link" className="mt-0 flex flex-col gap-6">
                    {linkPanel}
                </TabsContent>
                <TabsContent value="embed" className="mt-0">
                    <EmbedPanel url={url} formTitle={formTitle} />
                </TabsContent>
            </Tabs>
        </div>
    );
}
