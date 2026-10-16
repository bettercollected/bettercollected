'use client';
import Link from 'next/link';

import { Copy } from 'lucide-react';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { resolvePipesInText } from '@app/utils/answer-piping';
import UserAvatarDropDown from '@app/views/molecules/user-avatar-dropdown';
import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { describeRetention, retentionExplanation } from '@app/utils/retention';
import { LeafletIntroBand, LeafletSectionBar, LeafletTopRule } from '@app/views/molecules/form/leaflet-section';
import { leafletColours, mixHex, softInk, styleTokens } from '@app/views/molecules/theme/theme-shared';
import { FORM_COLUMN, columnPlacementClass, greetingAlignClass } from '@app/views/organism/layout/form-column';

export default function ThankyouPage({ isPreviewMode }: { isPreviewMode: boolean }) {
    const { toast } = useToast();
    const { t, language } = useRespondentLanguage();
    const standardForm = useAppSelector(selectResponderForm);
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const submissionUrl = window.PUBLIC_CONFIG?.HTTP_SCHEME + window.PUBLIC_CONFIG?.FORM_DOMAIN + '/' + workspace.workspaceName;
    const { responderId } = useResponderState();
    const [_, copyToClipboard] = useCopyToClipboard();
    const { formResponse } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();

    function getThankYouMessage() {
        const message = standardForm?.thankyouPage?.[0]?.message ? standardForm?.thankyouPage?.[0]?.message : formResponse.anonymize ? t('ENDING.SUBMITTED_ANONYMOUS') : t('ENDING.SUBMITTED');
        // Thank-you text supports text-token piping: "Thanks, {{field:<id>}}!"
        return resolvePipesInText(message, { slides: standardForm?.fields, answers: formResponse.answers ?? {}, hiddenValues });
    }

    // The heading is customizable (and pipeable) like the message; the classic
    // greeting stays as the default for forms that never set one.
    function getThankYouTitle() {
        const title = standardForm?.thankyouPage?.[0]?.title;
        if (!title) return t('ENDING.TITLE');
        return resolvePipesInText(title, { slides: standardForm?.fields, answers: formResponse.answers ?? {}, hiddenValues });
    }

    const handleOnCopy = (copyValue: string) => {
        copyToClipboard(copyValue);
        toast({
            description: t('ENDING.COPIED')
        });
    };
    // Forms created outside the builder (API/MCP) may have no thank-you page
    // at all — every read below must survive null/[] (the `!` + index here
    // crashed the post-submit screen with "Cannot read properties of null").
    const thankyouPage = standardForm?.thankyouPage?.[0];
    const theme = standardForm?.theme;
    // A quiet edge for the receipt card: the theme's border colour, softened.
    const cardEdge = theme?.tertiary && theme?.accent && /^#[0-9a-fA-F]{6}$/.test(theme.tertiary) && /^#[0-9a-fA-F]{6}$/.test(theme.accent) ? mixHex(theme.tertiary, theme.accent, 0.45) : '#D0D5DD';
    const receipt = auth.id && standardForm.settings?.showSubmissionNumber;

    if (styleTokens(theme?.style).key === 'leaflet') {
        // The leaflet's last page: the ending on the bar, the message in the
        // band, then what happens to the answers now, in plain words: how long
        // they are kept, the respondent's rights, and the receipt number.
        const rule = leafletColours(theme).rule;
        const retentionNote = retentionExplanation(standardForm?.settings);
        return (
            <>
                <UserAvatarDropDown disabled />
                <LeafletTopRule theme={theme} />
                <LeafletSectionBar theme={theme} title={getThankYouTitle()} layout={thankyouPage?.layout} headingLevel={1} />
                <LeafletIntroBand theme={theme} layout={thankyouPage?.layout}>
                    <p className="max-w-[62ch] text-pretty">{getThankYouMessage()}</p>
                </LeafletIntroBand>
                <div className={cn(FORM_COLUMN, columnPlacementClass(thankyouPage?.layout), 'flex flex-col items-start pt-8')} data-testid="thankyou-column">
                    <section aria-labelledby="leaflet-next" className="w-full" data-testid="leaflet-next">
                        <h2 id="leaflet-next" className="text-[22px] leading-tight" style={{ fontFamily: leafletSerif.style.fontFamily, fontWeight: 600, color: theme?.primary }}>
                            {t('ENDING.NEXT')}
                        </h2>
                        <ul className="mt-3 border-t text-base leading-[1.6]" style={{ borderColor: rule, color: theme?.primary }} lang={language}>
                            <li className="border-b py-3" style={{ borderColor: rule }}>
                                {describeRetention(standardForm?.settings, t, language)}
                                {retentionNote && <span style={{ color: softInk(theme) }}> {retentionNote}</span>}
                            </li>
                            <li className="border-b py-3" style={{ borderColor: rule }}>
                                {t('PRIVACY.RIGHTS_TEXT')}{' '}
                                {!isPreviewMode && (
                                    <a href={submissionUrl} target="_blank" rel="noopener noreferrer" className="font-medium underline underline-offset-2" style={{ color: theme?.secondary }}>
                                        {t('PRIVACY.RIGHTS_LINK')}
                                        <span className="sr-only"> {t('PRIVACY.OPENS_IN_NEW_TAB')}</span>
                                    </a>
                                )}
                            </li>
                        </ul>
                        {receipt && <SubmissionReceipt className="mt-6" edge={rule} responderId={responderId} submissionUrl={isPreviewMode ? '' : submissionUrl} onCopy={handleOnCopy} />}
                    </section>
                    {thankyouPage?.buttonText && (
                        <Button flat style={{ background: theme?.secondary }} className="mt-8 min-h-12 rounded-[4px] px-8 text-base font-semibold">
                            <Link href={isPreviewMode ? '' : thankyouPage.buttonLink || 'https://bettercollected.com'} target="_blank" referrerPolicy="no-referrer">
                                {thankyouPage.buttonText}
                            </Link>
                        </Button>
                    )}
                </div>
            </>
        );
    }

    return (
        <>
            <UserAvatarDropDown disabled />
            {/* Same column, alignment and vertical placement as the welcome
                page (form-column.ts, layout-wrapper.tsx). */}
            <div className={cn(FORM_COLUMN, columnPlacementClass(thankyouPage?.layout), 'flex flex-col bg-inherit pt-6', greetingAlignClass(thankyouPage?.layout))} data-testid="thankyou-column">
                <h1 className="max-w-[22ch] text-[32px] leading-[40px] font-bold tracking-[-0.02em] text-balance [overflow-wrap:anywhere] sm:text-[40px] sm:leading-[48px]" style={{ color: theme?.primary }}>
                    {getThankYouTitle()}
                </h1>
                <p className="mt-4 max-w-[60ch] text-[17px] leading-relaxed text-pretty" style={{ color: softInk(theme) }}>
                    {getThankYouMessage()}
                </p>
                {thankyouPage?.buttonText && (
                    <Button flat style={{ background: theme?.secondary }} className="mt-8 min-h-12 rounded-[8px] px-8 text-base font-semibold">
                        <Link href={isPreviewMode ? '' : thankyouPage.buttonLink || 'https://bettercollected.com'} target="_blank" referrerPolicy="no-referrer">
                            {thankyouPage.buttonText}
                        </Link>
                    </Button>
                )}
                {receipt && <SubmissionReceipt className="mt-8" edge={cardEdge} responderId={responderId} submissionUrl={isPreviewMode ? '' : submissionUrl} onCopy={handleOnCopy} />}
                {/* Attribution moved into the trust strip — the form's single
                    footer. A second floating "Powered by" here sat underneath
                    the fixed strip and the two overlapped. */}
            </div>
        </>
    );
}

/**
 * The receipt: the submission number, set in mono so every character can be
 * read back, with a copy button (a full 44px target) and the way to the
 * respondent's own submissions. White card, one quiet edge, no shadow.
 */
export function SubmissionReceipt({ responderId, submissionUrl, onCopy, edge, className }: { responderId?: string; submissionUrl: string; onCopy: (value: string) => void; edge: string; className?: string }) {
    const { t } = useRespondentLanguage();
    const standardForm = useAppSelector(selectResponderForm);
    const theme = standardForm?.theme;
    return (
        <div className={cn('flex w-full max-w-[440px] flex-col gap-2 rounded-[8px] border bg-white p-4 text-left', className)} style={{ borderColor: edge }} data-testid="submission-receipt">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <span className="text-[15px] font-semibold" style={{ color: theme?.primary }}>
                    {t('ENDING.SUBMISSION_NUMBER')}
                </span>
                <Link href={submissionUrl} className="text-[14px] font-medium underline underline-offset-2" style={{ color: theme?.secondary }}>
                    {t('ENDING.ALL_SUBMISSIONS')}
                </Link>
            </div>
            <span className="text-[14px] leading-relaxed text-black-700">{t('ENDING.SUBMISSION_NUMBER_HINT')}</span>
            <div className="mt-1 flex items-center justify-between gap-2 rounded-[6px] border pl-3" style={{ borderColor: edge }}>
                <span className="font-mono text-[15px] tracking-wide break-all tabular-nums" style={{ color: theme?.primary }}>
                    {responderId}
                </span>
                <button
                    type="button"
                    aria-label={t('ENDING.COPY')}
                    className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-[6px]"
                    style={{ color: theme?.secondary }}
                    onClick={() => {
                        responderId && onCopy(responderId);
                    }}
                >
                    <Copy className="h-4 w-4" aria-hidden="true" />
                </button>
            </div>
        </div>
    );
}
