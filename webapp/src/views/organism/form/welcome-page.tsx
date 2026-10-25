import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { Lock } from 'lucide-react';

import { FormTheme } from '@app/constants/theme';
import useFormContentLanguage from '@app/lib/hooks/use-form-content-language';
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
import { LeafletContents, LeafletIntroBand, LeafletSectionBar, LeafletTopRule } from '@app/views/molecules/form/leaflet-section';
import { formButtonStyle } from '@app/views/molecules/theme/theme-root';
import { actionInk, softInk, styleTokens } from '@app/views/molecules/theme/theme-shared';
import UserAvatarDropDown from '@app/views/molecules/user-avatar-dropdown';
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
    theme,
    formTitle,
    accountInStrip = false
}: Readonly<{
    isPreviewMode: boolean;
    welcomePageData?: any;
    theme?: FormTheme;
    /**
     * The title to show. Previews of a template or another form pass their
     * own; without it the page shows the form being answered (the store's).
     */
    formTitle?: string;
    /** The account control is in the organisation logo strip's row, not here. */
    accountInStrip?: boolean;
}>) {
    const standardForm = useAppSelector(selectResponderForm);
    const { t } = useRespondentLanguage();
    // The author's title and introduction, marked when in another language than the page.
    const contentLang = useFormContentLanguage();
    const { nextSlide } = useResponderState();
    const router = useRouter();
    const pathname = usePathname();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const responderSignInUrl = `/login?type=responder&workspace_id=${workspace.id}&redirect_to=${pathname}`;

    const welcomePage = welcomePageData || standardForm.welcomePage;
    const formTheme = theme || standardForm?.theme;
    const title = formTitle ?? standardForm?.title;
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
                    {standardForm?.settings?.requireVerifiedIdentity ? (
                        <>
                            {t('WELCOME.VERIFY_REQUIRED')} {verifyLink(t('WELCOME.VERIFY_NOW'))}
                        </>
                    ) : (
                        <>
                            {t('WELCOME.VIEW_LATER')} {verifyLink(t('WELCOME.VERIFY_EMAIL'))}
                        </>
                    )}
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
                                <Button className="mt-2 rounded-[8px] px-6" size="medium" data-primary-action>
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
                        // Filled with the action colour unless the theme's button style says otherwise (theme-root.ts).
                        style={formButtonStyle(formTheme?.secondary, leaflet ? '4px' : '8px')}
                        className={cn('form-button z-10 min-h-12 px-8 py-3 text-base font-semibold', leaflet ? 'rounded-[4px]' : 'rounded-[8px]')}
                        // The welcome page's primary action: the privacy panel never opens over it.
                        data-primary-action
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
                        {standardForm?.settings?.requireVerifiedIdentity && !auth.id ? t('WELCOME.VERIFY_AND_START') : startButtonText(welcomePage?.buttonText, t('WELCOME.START'))}
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
                {!accountInStrip && <UserAvatarDropDown responderSignInUrl={isPreviewMode ? '' : responderSignInUrl} />}
                {/* The same top row as the question pages: a hairline under 56px.
                    data-primary-content: where the content the trust panel must
                    leave in view begins (utils/panel-fit.ts). */}
                <div data-primary-content>
                    {/* With a logo strip the row only held the account control, now in the strip. */}
                    {!accountInStrip && <LeafletTopRule theme={formTheme} />}
                    <LeafletSectionBar theme={formTheme} title={<span lang={contentLang}>{title}</span>} layout={welcomePage?.layout} headingLevel={1} />
                    {welcomePage?.description && (
                        <LeafletIntroBand theme={formTheme} layout={welcomePage?.layout}>
                            <p className="max-w-[62ch] text-pretty" style={{ whiteSpace: 'pre-line' }} lang={contentLang}>
                                {welcomePage.description}
                            </p>
                        </LeafletIntroBand>
                    )}
                    <div className={cn(FORM_COLUMN, columnPlacementClass(welcomePage?.layout), 'flex flex-col pt-8')} data-testid="welcome-column">
                        <LeafletContents pages={standardForm?.fields} theme={formTheme} />
                        {actions}
                    </div>
                </div>
            </>
        );
    }

    return (
        <>
            {!accountInStrip && <UserAvatarDropDown responderSignInUrl={isPreviewMode ? '' : responderSignInUrl} />}

            {/* The page's Layout setting decides the alignment ("Centered"
                centres everything, "Left aligned" keeps one left edge); the
                layout wrapper centres the block vertically. pt-6 keeps the
                title clear of the account button in the top corner. */}
            <div className={cn(FORM_COLUMN, columnPlacementClass(welcomePage?.layout), 'flex flex-col pt-6', align)} data-testid="welcome-column" data-primary-content>
                {/* Title and introduction in the theme's ink (the introduction a
                    step lighter, still 7:1), on a measure that keeps long titles
                    to a few balanced lines. */}
                <h1 className="form-greeting-title max-w-[22ch] text-[32px] leading-[40px] font-bold tracking-[-0.02em] text-balance [overflow-wrap:anywhere] sm:text-[40px] sm:leading-[48px]" style={{ color: formTheme?.primary }} lang={contentLang}>
                    {title}
                </h1>
                {welcomePage?.description && (
                    <p className="mt-4 max-w-[60ch] text-[17px] leading-relaxed text-pretty" style={{ whiteSpace: 'pre-line', color: softInk(formTheme) }} lang={contentLang}>
                        {welcomePage?.description}
                    </p>
                )}

                {actions}
            </div>
        </>
    );
}
