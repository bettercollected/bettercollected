import Link from 'next/link';

import { FormSlideLayout } from '@app/models/enums/form';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import UserAvatarDropDown from '@app/views/molecules/UserAvatarDropdown';
import { Button } from '@app/shadcn/components/ui/button';
import { selectWorkspace } from '@app/store/workspaces/slice';
import environments from '@app/configs/environments';
import { selectAuth } from '@app/store/auth/slice';

export default function ThankyouPage({ isPreviewMode }: { isPreviewMode: boolean }) {
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const submissionUrl = environments.HTTP_SCHEME + '://' + environments.FORM_DOMAIN + '/' + workspace.workspaceName;
    return (
        <div
            className={cn('flex h-full w-full flex-col justify-center', standardForm?.thankyouPage![0]?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? 'items-start' : 'items-center')}
            style={{ background: standardForm.theme?.accent }}
        >
            <UserAvatarDropDown disabled />
            <div className=" flex h-full w-full max-w-[800px] flex-col justify-center">
                <div className="">
                    <div className="flex">
                        <span className="text-[40px] font-bold leading-[48px]">Thank You! 🎉</span>
                    </div>
                    <div className="p2-new text-black-700 mt-4">{standardForm?.thankyouPage?.[0]?.message || 'Your response is successfully submitted.'}</div>
                    {standardForm?.thankyouPage && standardForm?.thankyouPage[0].buttonText && (
                        <Button style={{ background: standardForm.theme?.secondary }} className="mt-14">
                            <Link href={isPreviewMode ? '' : standardForm?.thankyouPage[0].buttonLink || 'https://bettercollected.com'} target="_blank" referrerPolicy="no-referrer">
                                {standardForm?.thankyouPage[0].buttonText}
                            </Link>
                        </Button>
                    )}
                    {auth.id && (
                        <div className="p2-new mt-10 max-w-[400px] rounded-lg bg-white p-4">
                            <div className=" text-black-700">You can view or request deletion of this response.</div>
                            <div>
                                <Link href={isPreviewMode ? '' : submissionUrl} className="text-blue-500">
                                    See all your submissions
                                </Link>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
