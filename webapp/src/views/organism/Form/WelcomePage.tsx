import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { FormTheme } from '@app/constants/theme';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { selectWorkspace } from '@app/store/workspaces/slice';
import UserAvatarDropDown from '@app/views/molecules/UserAvatarDropdown';
import LockIcon from '@Components/Common/Icons/lock';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';

export default function WelcomePage({
    isPreviewMode,
    welcomePageData,
    theme
}: Readonly<{
    isPreviewMode: boolean;
    welcomePageData?: any;
    theme?: FormTheme;
}>) {
    const standardForm = useAppSelector(selectForm);
    const { nextSlide } = useResponderState();
    const router = useRouter();
    const pathname = usePathname();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const responderSignInUrl = `/login?type=responder&workspace_id=${workspace.id}&redirect_to=${pathname}`;

    const welcomePage = welcomePageData || standardForm.welcomePage;
    const formTheme = theme || standardForm?.theme;

    return (
        <>
            <div className={cn('flex h-full w-full flex-col justify-center px-8', welcomePage?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? 'items-start' : 'items-center')}>
                <UserAvatarDropDown responderSignInUrl={isPreviewMode ? '' : responderSignInUrl} />

                <div className="flex h-full w-full max-w-[800px] flex-col justify-center">
                    <div className="mb-12">
                        <div className="text-[40px] font-bold leading-[48px]">{welcomePage?.title}</div>
                        {welcomePage?.description && (
                            <div className="text-black-700 mt-4 " style={{ whiteSpace: 'pre-line' }}>
                                {welcomePage?.description}
                            </div>
                        )}
                    </div>

                    {!standardForm?.settings?.private && !auth.id && (
                        <>
                            {standardForm?.settings?.requireVerifiedIdentity ? (
                                <>
                                    To fill this form you need to verify your identity.
                                    <span>
                                        <Link href={isPreviewMode ? '' : responderSignInUrl} className="text-black-800 font-medium underline">
                                            Verify Now
                                        </Link>
                                    </span>
                                </>
                            ) : (
                                <div className="mb-4 flex flex-wrap gap-1">
                                    To view your response later{' '}
                                    <span>
                                        <Link href={isPreviewMode ? '' : responderSignInUrl} className="text-black-800 font-medium underline">
                                            Verify Email
                                        </Link>
                                    </span>
                                </div>
                            )}
                        </>
                    )}

                    {standardForm?.settings?.private && (
                        <>
                            {!auth.id ? (
                                <div className="flex flex-col gap-2">
                                    <div className="flex items-center gap-4">
                                        <div className="bg-black-900 rounded-full p-2 text-white">
                                            <LockIcon width={24} height={24} className="text-white" />
                                        </div>
                                        <span>Private Form</span>
                                    </div>
                                    <div className="text-black-700 flex max-w-[339px] flex-wrap gap-1 text-xs">
                                        This form is limited to certain people only. Please verify your identity to get access.
                                        <span>
                                            <Link href={isPreviewMode ? '' : responderSignInUrl} className="text-black-800 font-medium underline">
                                                <Button className="mt-4 px-6" size={ButtonSize.Medium}>
                                                    {' '}
                                                    Verify now
                                                </Button>
                                            </Link>
                                        </span>{' '}
                                    </div>
                                </div>
                            ) : (
                                <>{standardForm?.unauthorized && <>You do not have access to this form. Switch to a different account with access to continue. If this is a mistake contact the owner of this form.</>}</>
                            )}
                        </>
                    )}

                    {(!standardForm?.settings?.private || (standardForm?.settings?.private && auth.id && !standardForm?.unauthorized)) && (
                        <div className="invisible lg:visible">
                            <Button
                                style={{ background: formTheme?.secondary }}
                                className="z-10 mt-2 rounded px-8 py-3"
                                size="medium"
                                onClick={() => {
                                    if (!auth.id && standardForm?.settings?.requireVerifiedIdentity) {
                                        router.push(responderSignInUrl);
                                    } else {
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
            <div className="border-black-200 flex absolute bottom-0 w-full border-t p-4 lg:hidden" style={{ background: formTheme?.accent }}>
                <Button
                    style={{ background: formTheme?.secondary }}
                    className="z-10 mt-2 w-full rounded px-8 py-3"
                    size="medium"
                    onClick={() => {
                        if (!auth.id && standardForm?.settings?.requireVerifiedIdentity) {
                            router.push(responderSignInUrl);
                        } else {
                            nextSlide();
                            return;
                        }
                    }}
                >
                    {standardForm?.settings?.requireVerifiedIdentity && !auth.id ? 'Verify and Start' : standardForm?.welcomePage?.buttonText || 'Start'}
                </Button>
            </div>
        </>
    );
}
