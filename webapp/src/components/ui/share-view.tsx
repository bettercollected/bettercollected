'use client';

import { ReactNode, useState } from 'react';

import cn from 'classnames';
import { Check, Copy, ExternalLink } from 'lucide-react';
import { FacebookShareButton, LinkedinShareButton, TwitterShareButton } from 'react-share';

import { Facebook } from '@app/components/icons/brands/facebook';
import { Linkedin } from '@app/components/icons/brands/linkedin';
import { Twitter } from '@app/components/icons/brands/twitter';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';

type SizeNames = 'large' | 'small';

interface Props {
    url: string;
    title?: string;
    showCopy?: boolean;
    iconSize?: SizeNames;
    className?: string;
}

const SocialButton = ({ children, label }: { children: ReactNode; label: string }) => (
    <span
        aria-label={label}
        className="border-black-200 text-black-700 hover:border-brand-300 hover:bg-brand-100 flex h-10 w-10 items-center justify-center rounded-full border bg-white transition-colors"
    >
        {children}
    </span>
);

export default function ShareView({ url, title, showCopy = true, className }: Props) {
    const [, copyToClipboard] = useCopyToClipboard();
    const { toast } = useToast();
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        copyToClipboard(url);
        setCopied(true);
        toast({ description: 'Link copied to clipboard' });
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className={cn('flex flex-col gap-6', className)}>
            <div className="flex flex-col gap-1.5">
                <h2 className="text-black-900 text-lg font-semibold leading-snug">{title || 'Share this form'}</h2>
                {/* Honest about what the link does — no coercion, no surprises. */}
                <p className="text-black-600 text-sm leading-relaxed">Anyone with this link can open and respond to your form.</p>
            </div>

            {showCopy && (
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <div className="border-black-300 bg-black-100 flex min-w-0 flex-1 items-center gap-2 rounded-lg border px-3.5 py-3">
                        <span className="text-black-800 min-w-0 flex-1 truncate text-sm" title={url}>
                            {url}
                        </span>
                        <a href={url} target="_blank" rel="noopener noreferrer" aria-label="Open form in a new tab" className="text-black-500 hover:text-brand-500 shrink-0 transition-colors">
                            <ExternalLink className="h-4 w-4" />
                        </a>
                    </div>
                    <Button size="medium" variant="primary" onClick={handleCopy} icon={copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />} className="shrink-0">
                        {copied ? 'Copied' : 'Copy link'}
                    </Button>
                </div>
            )}

            <div className="flex flex-col gap-2.5">
                <span className="text-black-500 text-xs font-medium uppercase tracking-wide">Or share on</span>
                <div className="flex items-center gap-3">
                    <TwitterShareButton url={url}>
                        <SocialButton label="Share on X">
                            <Twitter className="h-[18px] w-[18px]" />
                        </SocialButton>
                    </TwitterShareButton>
                    <FacebookShareButton url={url}>
                        <SocialButton label="Share on Facebook">
                            <Facebook className="h-[18px] w-[18px]" />
                        </SocialButton>
                    </FacebookShareButton>
                    <LinkedinShareButton url={url}>
                        <SocialButton label="Share on LinkedIn">
                            <Linkedin className="h-[18px] w-[18px]" />
                        </SocialButton>
                    </LinkedinShareButton>
                </div>
            </div>
        </div>
    );
}
