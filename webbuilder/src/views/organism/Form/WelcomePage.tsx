import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { Globe, Lock } from 'lucide-react';

import environments from '@app/configs/environments';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useAuthAtom } from '@app/store/jotai/auth';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useResponderState } from '@app/store/jotai/responderFormState';
import useWorkspace from '@app/store/jotai/workspace';
import UserAvatarDropDown from '@app/views/molecules/UserAvatarDropdown';

export default function WelcomePage({ isPreviewMode }: { isPreviewMode: boolean }) {
    const { standardForm } = useStandardForm();
    const { nextSlide } = useResponderState();
    const router = useRouter();
    const pathname = usePathname();
    const { workspace } = useWorkspace();
    const { authState } = useAuthAtom();
    const responderSignInUrl = `${environments.NEXT_PUBLIC_HTTP_SCHEME}://${environments.NEXT_PUBLIC_V1_CLIENT_ENDPOINT_DOMAIN}/login?type=responder&workspace_id=${workspace.id}&redirect_to=${environments.NEXT_PUBLIC_HTTP_SCHEME}://${environments.NEXT_PUBLIC_V2_CLIENT_ENDPOINT_DOMAIN}${pathname}`;

    return (
        <div
            className={cn(
                'flex h-full w-full flex-col justify-center',
                standardForm.welcomePage?.layout ===
                    FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN
                    ? 'items-start'
                    : 'items-center'
            )}
        >
            <UserAvatarDropDown
                responderSignInUrl={isPreviewMode ? '' : responderSignInUrl}
            />

            <div className="flex h-full w-full max-w-[800px] flex-col justify-center">
                <div className="text-[40px] font-bold leading-[48px]">
                    {standardForm.welcomePage?.title}
                </div>
                {standardForm?.description && (
                    <div className="mt-4 text-black-700 ">
                        {standardForm?.description}
                    </div>
                )}
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
                    <div className="mt-2 text-xs text-black-700">
                        {standardForm?.settings?.requireVerifiedIdentity ? (
                            <>
                                The form you are trying to access is limited to certain
                                groups. Please verify your account to get access.
                            </>
                        ) : (
                            <>
                                The form you are trying to access is public, but you can
                                always sign in to view your response later.{' '}
                                <span>
                                    <Link
                                        href={isPreviewMode ? '' : '/login'}
                                        className="text-blue-500 "
                                    >
                                        {' '}
                                        Verify Account
                                    </Link>
                                </span>
                            </>
                        )}
                    </div>
                </div>
                <div className="mt-6">
                    <Button
                        style={{ background: standardForm.theme?.secondary }}
                        className="z-10 mt-12 rounded px-8 py-3"
                        size="medium"
                        onClick={() => {
                            if (
                                !authState.id &&
                                standardForm?.settings?.requireVerifiedIdentity
                            ) {
                                router.push(responderSignInUrl);
                            } else {
                                nextSlide();
                                return;
                            }
                        }}
                    >
                        {standardForm?.settings?.requireVerifiedIdentity &&
                        !authState.id
                            ? 'Verify and Start'
                            : 'Start'}
                    </Button>
                </div>
            </div>
        </div>
    );
}
