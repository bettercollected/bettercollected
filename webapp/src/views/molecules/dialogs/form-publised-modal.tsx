'use client';

import { useEffect, useRef, useState } from 'react';

import { Check, Copy, ExternalLink } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import DaybreakArt from '@app/components/ui/daybreak-art';
import { Button, buttonClassName } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/form-utils';

/**
 * The moment a form goes live. The motif band and a check mark say it is done
 * (the mark is a shape, not a colour); the link is the centre of the dialog with
 * its Copy button; two next steps follow as buttons: open the form, and the
 * other ways to share it. Copying is answered in the dialog itself, in a status
 * line a screen reader announces, not only in a toast that disappears.
 * No confetti: the check settles once, and not at all under reduced motion.
 */
export default function FormPublishedModal(props: any) {
    const { t } = useTranslation('builder');
    const workspace = useAppSelector(selectWorkspace);
    const standardForm = useAppSelector(selectForm);
    // '' nothing yet, 'copied', or 'failed' (the browser refused the clipboard)
    const [copyState, setCopyState] = useState<'' | 'copied' | 'failed'>('');
    const resetTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
    useEffect(() => () => clearTimeout(resetTimer.current), []);

    const shareUrl = getFormShareURL(standardForm, workspace);
    const sharingUrl = `${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN}/${workspace.workspaceName}/dashboard/forms/${standardForm.formId}?view=FormLinks`;

    const handleCopy = async () => {
        let next: 'copied' | 'failed' = 'copied';
        try {
            await navigator.clipboard.writeText(shareUrl);
        } catch {
            next = 'failed';
        }
        setCopyState(next);
        clearTimeout(resetTimer.current);
        resetTimer.current = setTimeout(() => setCopyState(''), next === 'copied' ? 3000 : 6000);
    };

    // min-w-0 on the root matters: DialogContent is display:grid, and a grid
    // item's implicit min-width:auto lets the unbreakable URL dictate the
    // width, overflowing the dialog instead of truncating.
    return (
        <div className="flex w-full max-w-full min-w-0 flex-col overflow-hidden sm:rounded">
            <div className="relative h-[96px] bg-brand-tint sm:h-[112px]">
                <DaybreakArt spark={false} />
                <span
                    data-testid="published-mark"
                    className="absolute bottom-0 left-6 flex h-12 w-12 translate-y-1/2 items-center justify-center rounded-full border border-hairline-strong bg-surface text-ok motion-safe:animate-in motion-safe:duration-500 motion-safe:fade-in-0 motion-safe:zoom-in-50 sm:left-8"
                >
                    <Check className="h-6 w-6" strokeWidth={2.5} aria-hidden="true" />
                </span>
            </div>

            <div className="flex flex-col gap-4 p-6 pt-10 sm:p-8 sm:pt-11">
                <div className="flex flex-col gap-1.5">
                    <h2 className="m-0 text-xl leading-snug font-semibold tracking-title-sm text-ink">{t('PUBLISHED_MODAL.TITLE')}</h2>
                    {/* Honest about what publishing means: the same line the Share modal uses. */}
                    <p className="m-0 text-sm leading-relaxed text-copy">{t('PUBLISHED_MODAL.BODY')}</p>
                </div>

                <div className="flex flex-col gap-2">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
                        <div className="flex min-w-0 flex-1 items-center rounded border border-hairline-strong bg-sunken px-3.5 py-3">
                            <span className="min-w-0 flex-1 truncate font-mono text-sm text-ink select-all" title={shareUrl} data-testid="published-link">
                                {shareUrl}
                            </span>
                        </div>
                        <Button
                            size="medium"
                            variant="primary"
                            onClick={handleCopy}
                            icon={copyState === 'copied' ? <Check className="h-4 w-4" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
                            className="shrink-0"
                            data-umami-event={'PublishModal Copy Button'}
                        >
                            {copyState === 'copied' ? t('PUBLISHED_MODAL.COPIED') : t('PUBLISHED_MODAL.COPY')}
                        </Button>
                    </div>
                    {/* Always in the page, so the announcement reaches a screen reader when the text arrives. */}
                    <p role="status" className="m-0 min-h-5 text-sm leading-5 text-copy">
                        {copyState === 'copied' ? t('PUBLISHED_MODAL.COPIED_TOAST') : copyState === 'failed' ? t('PUBLISHED_MODAL.COPY_FAILED') : ''}
                    </p>
                </div>

                <div className="flex flex-col gap-3 sm:flex-row">
                    <a href={shareUrl} target="_blank" rel="noopener noreferrer" data-umami-event={'PublishModal Open Form Link'} className={buttonClassName({ variant: 'tertiary', size: 'medium', className: 'sm:flex-1' })}>
                        <ExternalLink className="h-4 w-4" aria-hidden="true" />
                        {t('PUBLISHED_MODAL.OPEN_FORM')}
                        <span className="sr-only"> ({t('PUBLISHED_MODAL.NEW_TAB')})</span>
                    </a>
                    <a href={sharingUrl} data-umami-event={'PublishModal Goto Settings Link'} className={buttonClassName({ variant: 'tertiary', size: 'medium', className: 'sm:flex-1' })}>
                        {t('PUBLISHED_MODAL.MORE_SHARE')}
                    </a>
                </div>
            </div>
        </div>
    );
}
