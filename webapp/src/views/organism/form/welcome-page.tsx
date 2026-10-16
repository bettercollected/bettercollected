import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { Lock } from 'lucide-react';

import { FormTheme } from '@app/constants/theme';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useSendFlowEventMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getFlowSessionId } from '@app/utils/flow-session';
import UserAvatarDropDown from '@app/views/molecules/user-avatar-dropdown';
import { LeafletContents, LeafletIntroBand, LeafletSectionBar, LeafletTopRule } from '@app/views/molecules/form/leaflet-section';
import { actionInk, softInk, styleTokens } from '@app/views/molecules/theme/theme-shared';
import { FORM_COLUMN, columnPlacementClass, greetingAlignClass } from '@app/views/organism/layout/form-column';

/**
 * The start button's text: the creator's own wording as written, else the
 * default in the respondent's language. A button left at the default
 * ("Start") counts as the default.
 */
export function startButtonText(creatorText: string | undefined, translatedDefault: string): string {
    const text = creatorText?.trim();
    return text && text !== 'Start' ? text : translatedDefault;
}

export default function WelcomePage({
    isPreviewMode,
    welcomePageData,
    theme
}: Readonly<{
    isPreviewMode: boolean;
    welcomePageData?: any;
    theme?: FormTheme;
}>) {
    const standardForm = useAppSelector(selectResponderForm);
    const { t } = useRespondentLanguage();
    const { nextSlide } = useResponderState();
    const router = useRouter();
    const pathname = usePathname();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const responderSignInUrl = `/login?type=responder&workspace_id=${workspace.id}&redirect_to=${pathname}`;

    const welcomePage = welcomePageData || standardForm.welcomePage;
    const formTheme = theme || standardForm?.theme;
    const leaflet = styleTokens(formTheme?.style).key === 'leaflet';
    // A leaflet reads from one left edge; the column still follows the page's placement.
    const align = leaflet ? 'items-start text-left' : greetingAlignClass(welcomePage?.layout);

    const [sendFlowEvent] = useSendFlowEventMutation();
    // Anonymous drop-off breadcrumb for "started the form" — never in preview.
    const emitStart = () => {
        const firstPageId = standardForm?.fields?.[0]?.id;
        if (isPreviewMode || !workspace?.id || !standardForm?.formId || !firstPageId) return;
        sendFlowEvent({ workspaceId: workspace.id, formId: standardForm.formId, sessionId: getFlowSessionId(standardForm.formId), fromPage: '__welcome__', toPage: firstPageId }).catch(() => {});
    };

    const verifyLink = (label: string) => (
        <Link href={isPreviewMode ? '' : responderSignInUrl} className="font-medium underline underline-offset-2" style={{ color: actionInk(formTheme) }}>
            {label}
        </Link>
    );

    // Notes and the start button: one group, set apart from the title block.
    const actions = (
        <div className={cn('mt-8 flex w-full flex-col gap-4', align)}>
            {!standardForm?.settings?.private && !auth.id && (
                <p className="text-base" style={{ color: softInk(formTheme) }}>
                    {standardForm?.settings?.requireVerifiedIdentity ? <>{t('WELCOME.VERIFY_REQUIRED')} {verifyLink(t('WELCOME.VERIFY_NOW'))}</> : <>{t('WELCOME.VIEW_LATER')} {verifyLink(t('WELCOME.VERIFY_EMAIL'))}</>}
                </p>
            )}

            {standardForm?.settings?.private && (
                <>
                    {!auth.id ? (
                        <div className={cn('flex flex-col gap-2', align)}>
                            <div className="flex items-center gap-4">
                                <div className="rounded-full bg-black-900 p-2 text-white">
                                    <Lock width={24} height={24} className="text-white" />
                                </div>
                                <span>{t('WELCOME.PRIVATE')}</span>
                            </div>
                            <p className="max-w-[339px] text-xs text-black-700">{t('WELCOME.PRIVATE_TEXT')}</p>
                            <Link href={isPreviewMode ? '' : responderSignInUrl} className="font-medium text-black-800 underline">
                                <Button className="mt-2 rounded-[8px] px-6" size="medium">
                                    {t('WELCOME.VERIFY_NOW')}
                                </Button>
                            </Link>
                        </div>
                    ) : (
                        <>{standardForm?.unauthorized && <p>{t('WELCOME.NO_ACCESS')}</p>}</>
                    )}
                </>
            )}

            {(!standardForm?.settings?.private || (standardForm?.settings?.private && auth.id && !standardForm?.unauthorized)) && (
                <div>
                    <Button
                        flat
                        style={{ background: formTheme?.secondary }}
                        className={cn('z-10 min-h-12 px-8 py-3 text-base font-semibold', leaflet ? 'rounded-[4px]' : 'rounded-[8px]')}
                        size="medium"
                        onClick={() => {
                            if (!auth.id && standardForm?.settings?.requireVerifiedIdentity) {
                                router.push(responderSignInUrl);
                            } else {
                                emitStart();
                                nextSlide();
                                return;
                            }
                        }}
                    >
                        {standardForm?.settings?.requireVerifiedIdentity && !auth.id ? t('WELCOME.VERIFY_AND_START') : startButtonText(standardForm?.welcomePage?.buttonText, t('WELCOME.START'))}
                    </Button>
                </div>
            )}
        </div>
    );

    if (leaflet) {
        // The leaflet cover: the form's title on the section bar, its
        // introduction in the pale band, then what the form holds and Start.
        return (
            <>
                <UserAvatarDropDown responderSignInUrl={isPreviewMode ? '' : responderSignInUrl} />
                {/* The same top row as the question pages: a hairline under 56px. */}
                <LeafletTopRule theme={formTheme} />
                <LeafletSectionBar theme={formTheme} title={standardForm?.title} layout={welcomePage?.layout} headingLevel={1} />
                {welcomePage?.description && (
                    <LeafletIntroBand theme={formTheme} layout={welcomePage?.layout}>
                        <p className="max-w-[62ch] text-pretty" style={{ whiteSpace: 'pre-line' }}>
                            {welcomePage.description}
                        </p>
                    </LeafletIntroBand>
                )}
                <div className={cn(FORM_COLUMN, columnPlacementClass(welcomePage?.layout), 'flex flex-col pt-8')} data-testid="welcome-column">
                    <LeafletContents pages={standardForm?.fields} theme={formTheme} />
                    {actions}
                </div>
            </>
        );
    }

    return (
        <>
            <UserAvatarDropDown responderSignInUrl={isPreviewMode ? '' : responderSignInUrl} />

            {/* The page's Layout setting decides the alignment ("Centered"
                centres everything, "Left aligned" keeps one left edge); the
                layout wrapper centres the block vertically. pt-6 keeps the
                title clear of the account button in the top corner. */}
            <div className={cn(FORM_COLUMN, columnPlacementClass(welcomePage?.layout), 'flex flex-col pt-6', align)} data-testid="welcome-column">
                {/* Title and introduction in the theme's ink (the introduction a
                    step lighter, still 7:1), on a measure that keeps long titles
                    to a few balanced lines. */}
                <h1 className="max-w-[22ch] text-[32px] leading-[40px] font-bold tracking-[-0.02em] text-balance [overflow-wrap:anywhere] sm:text-[40px] sm:leading-[48px]" style={{ color: formTheme?.primary }}>
                    {standardForm?.title}
                </h1>
                {welcomePage?.description && (
                    <p className="mt-4 max-w-[60ch] text-[17px] leading-relaxed text-pretty" style={{ whiteSpace: 'pre-line', color: softInk(formTheme) }}>
                        {welcomePage?.description}
                    </p>
                )}

{actions}
            </div>
        </>
    );
}
