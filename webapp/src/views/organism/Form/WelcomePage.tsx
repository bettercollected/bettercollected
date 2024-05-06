import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { Globe, Lock } from 'lucide-react';

import environments from '@app/configs/environments';
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
    const responderSignInUrl = `${environments.HTTP_SCHEME}${environments.FORM_DOMAIN}/login?type=responder&workspace_id=${workspace.id}&redirect_to=${environments.HTTP_SCHEME}${environments.FORM_DOMAIN}${pathname}`;

    const welcomePage = welcomePageData || standardForm.welcomePage;
    const formTheme = theme || standardForm?.theme;
    return (
        <div className={cn('flex h-full w-full flex-col justify-center', welcomePage?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? 'items-start' : 'items-center')}>
            <UserAvatarDropDown responderSignInUrl={isPreviewMode ? '' : responderSignInUrl} />

            <div className="flex h-full w-full max-w-[800px] flex-col justify-center">
                <div className="text-[40px] font-bold leading-[48px]">{welcomePage?.title}</div>
                {welcomePage?.description && (
                    <div className="text-black-700 mt-4 " style={{ whiteSpace: 'pre-line' }}>
                        {welcomePage?.description}
                    </div>
                )}
                {!auth.id && !isPreviewMode && (
                    <div className="mt-16 flex max-w-[421px] flex-col rounded-lg bg-white bg-opacity-50 p-4">
                        <div className="flex items-center gap-2">
                            {standardForm?.settings?.requireVerifiedIdentity ? (
                                <>
                                    <div className="rounded-full bg-red-100 p-[5px]">
                                        <Lock color="#EA400E" />
                                    </div>
                                    <span>This form is private</span>
                                </>
                            ) : (
                                <>
                                    <div className="rounded-full bg-green-100 p-[5px]">
                                        <Globe color="#2DBB7F" />
                                    </div>
                                    <span>This form is public</span>
                                </>
                            )}
                        </div>
                        <div className="text-black-700 mt-2 text-xs">
                            {standardForm?.settings?.requireVerifiedIdentity ? (
                                <>The form you are trying to access is limited to certain groups. Please verify your account to get access.</>
                            ) : (
                                <>
                                    The form you are trying to access is public, but you can always sign in to view your response later.{' '}
                                    <span>
                                        <Link href={isPreviewMode ? '' : '/login'} className="text-blue-500 ">
                                            {' '}
                                            Verify Account
                                        </Link>
                                    </span>
                                </>
                            )}
                        </div>
                    </div>
                )}
                {standardForm.settings?.private || standardForm.settings?.hidden ? (
                    <div className="mt-16 flex max-w-[421px] flex-col rounded-lg bg-white bg-opacity-50 p-4">
                        <span>This form is private and only allowed for certain Groups.</span>
                    </div>
                ) : (
                    <div className="mt-6">
                        <Button
                            style={{ background: formTheme?.secondary }}
                            className="z-10 mt-12 rounded px-8 py-3"
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
                            {standardForm?.settings?.requireVerifiedIdentity && !auth.id ? 'Verify and Start' : 'Start'}
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
}
