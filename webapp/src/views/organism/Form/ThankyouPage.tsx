import Link from 'next/link';

import Copy from '@Components/Common/Icons/Common/Copy';
import Logo from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { selectWorkspace } from '@app/store/workspaces/slice';
import UserAvatarDropDown from '@app/views/molecules/UserAvatarDropdown';
import { toast } from 'react-toastify';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

export default function ThankyouPage({ isPreviewMode }: { isPreviewMode: boolean }) {
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const submissionUrl = environments.HTTP_SCHEME + environments.FORM_DOMAIN + '/' + workspace.workspaceName;
    const { responderId } = useResponderState();
    const [_, copyToClipboard] = useCopyToClipboard();

    const handleOnCopy = (copyValue: string) => {
        copyToClipboard(copyValue);
        toast('Copied', {
            type: 'info'
        });
    };
    return (
        <div
            className={cn('flex h-full w-full flex-col justify-center', standardForm?.thankyouPage![0]?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? 'items-start' : 'items-center')}
            style={{ background: standardForm.theme?.accent }}
        >
            <UserAvatarDropDown disabled />
            <div className=" flex h-full w-full max-w-[800px] flex-col justify-between">
                {/* <div className=""> */}
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
                    <div className="p2-new mt-10 flex max-w-[400px] flex-col gap-2 rounded-lg bg-white/50 p-4 ">
                        <div className="flex flex-row justify-between">
                            <span className="p3-new text-black-800">Submission Number</span>
                            <Link href={isPreviewMode ? '' : submissionUrl} className="text-blue-500">
                                See all your submissions
                            </Link>
                        </div>
                        <span className="p4-new text-black-700">Use this submission number to view or request deletion of this response.</span>
                        <div className="bg-black-100/50 flex justify-between rounded-lg px-4 py-2">
                            <span className="p4-new text-black-700">{responderId}</span>
                            <Copy
                                className="text-brand-500 h-4 w-4 cursor-pointer"
                                onClick={() => {
                                    responderId && handleOnCopy(responderId);
                                }}
                            />
                        </div>
                    </div>
                )}
                <div className="bottom-8 mt-4 flex flex-row gap-2 lg:absolute lg:m-0 ">
                    <span className="body3 text-black-700">Powered by:</span>
                    <Logo showProTag={false} isLink={false} isCustomDomain className="h-[14px] w-fit" />
                </div>
                {/* </div> */}
            </div>
        </div>
    );
}
