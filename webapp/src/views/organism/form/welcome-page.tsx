import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { Lock } from 'lucide-react';

import { FormTheme } from '@app/constants/theme';
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
import { FORM_COLUMN, columnPlacementClass, greetingAlignClass } from '@app/views/organism/layout/form-column';

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
    const { nextSlide } = useResponderState();
    const router = useRouter();
    const pathname = usePathname();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const responderSignInUrl = `/login?type=responder&workspace_id=${workspace.id}&redirect_to=${pathname}`;

    const welcomePage = welcomePageData || standardForm.welcomePage;
    const formTheme = theme || standardForm?.theme;
    const align = greetingAlignClass(welcomePage?.layout);

    const [sendFlowEvent] = useSendFlowEventMutation();
    // Anonymous drop-off breadcrumb for "started the form" — never in preview.
    const emitStart = () => {
        const firstPageId = standardForm?.fields?.[0]?.id;
        if (isPreviewMode || !workspace?.id || !standardForm?.formId || !firstPageId) return;
        sendFlowEvent({ workspaceId: workspace.id, formId: standardForm.formId, sessionId: getFlowSessionId(standardForm.formId), fromPage: '__welcome__', toPage: firstPageId }).catch(() => {});
    };

    const verifyLink = (label: string) => (
        <Link href={isPreviewMode ? '' : responderSignInUrl} className="font-medium text-black-800 underline underline-offset-2">
            {label}
        </Link>
    );

    return (
        <>
            <UserAvatarDropDown responderSignInUrl={isPreviewMode ? '' : responderSignInUrl} />

            {/* The page's Layout setting decides the alignment ("Centered"
                centres everything, "Left aligned" keeps one left edge); the
                layout wrapper centres the block vertically. pt-6 keeps the
                title clear of the account button in the top corner. */}
            <div className={cn(FORM_COLUMN, columnPlacementClass(welcomePage?.layout), 'flex flex-col pt-6', align)} data-testid="welcome-column">
                <h1 className="text-[32px] leading-[40px] font-bold text-balance [overflow-wrap:anywhere] sm:text-[40px] sm:leading-[48px]">{standardForm?.title}</h1>
                {welcomePage?.description && (
                    <p className="mt-4 max-w-[60ch] text-base leading-relaxed text-pretty text-black-700" style={{ whiteSpace: 'pre-line' }}>
                        {welcomePage?.description}
                    </p>
                )}

                {/* Notes and the start button: one group, set apart from the title block. */}
                <div className={cn('mt-8 flex w-full flex-col gap-4', align)}>
                    {!standardForm?.settings?.private && !auth.id && (
                        <p className="text-base text-black-700">
                            {standardForm?.settings?.requireVerifiedIdentity ? <>To fill this form you need to verify your identity. {verifyLink('Verify Now')}</> : <>To view your response later {verifyLink('Verify Email')}</>}
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
                                        <span>Private Form</span>
                                    </div>
                                    <p className="max-w-[339px] text-xs text-black-700">This form is limited to certain people only. Please verify your identity to get access.</p>
                                    <Link href={isPreviewMode ? '' : responderSignInUrl} className="font-medium text-black-800 underline">
                                        <Button className="mt-2 rounded-[8px] px-6" size="medium">
                                            Verify now
                                        </Button>
                                    </Link>
                                </div>
                            ) : (
                                <>{standardForm?.unauthorized && <p>You do not have access to this form. Switch to a different account with access to continue. If this is a mistake contact the owner of this form.</p>}</>
                            )}
                        </>
                    )}

                    {(!standardForm?.settings?.private || (standardForm?.settings?.private && auth.id && !standardForm?.unauthorized)) && (
                        <div>
                            <Button
                                flat
                                style={{ background: formTheme?.secondary }}
                                className="z-10 rounded-[8px] px-8 py-3 text-base font-semibold"
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
                                {standardForm?.settings?.requireVerifiedIdentity && !auth.id ? 'Verify and Start' : standardForm?.welcomePage?.buttonText || 'Start'}
                            </Button>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
