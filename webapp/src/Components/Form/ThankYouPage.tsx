import React from 'react';

import Image from 'next/image';
import { useRouter } from 'next/router';

import CopyIcon from '@Components/Common/Icons/Common/Copy';
import SmallLogo from '@Components/Common/Icons/Common/SmallLogo';
import { toast } from 'react-toastify';

import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface IThankYouPageProps {
    form: StandardFormDto;
    isDisabled?: boolean;
    showSubmissionNumber?: boolean;
    submissionNumber?: string;
}

ThankYouPage.defaultProps = {
    isDisabled: false
};

export default function ThankYouPage({ form, isDisabled, showSubmissionNumber, submissionNumber }: IThankYouPageProps) {
    const router = useRouter();
    const auth = useAppSelector(selectAuth);
    const workspace = useAppSelector(selectWorkspace);
    const isCustomDomain = window?.location.host !== environments.CLIENT_DOMAIN;

    const [_, copyToClipboard] = useCopyToClipboard();

    const onClickGoToMyResponse = () => {
        if (isCustomDomain) {
            router.push('/?view=my-submissions');
        } else {
            router.push(`/${workspace.workspaceName}?view=my-submissions`);
        }
    };

    const workspaceResponseUrl = isCustomDomain ? '/?view=my-submissions' : `/${workspace.workspaceName}?view=my-submissions`;

    return (
        <div className="flex w-full flex-col items-center justify-start h-full text-center">
            <div className="w-full aspect-banner-mobile  lg:aspect-thank_you_cover  relative flex items-center justify-center">
                <Image src="/images/thankyou_cover.png" layout="fill" objectFit="cover" alt="ALternative" />
                <svg
                    className="w-16 h-16 md:w-20 md:h-20  lg:w-24 lg:h-24"
                    viewBox="0 0 100 100"
                    fill="none"
                    style={{
                        zIndex: 1
                    }}
                    xmlns="http://www.w3.org/2000/svg"
                >
                    <circle cx="50" cy="50" r="50" fill="white" />
                    <path d="M29 55.6889L39.4612 66L71.9268 34" stroke="#2DBB7F" strokeWidth="4" strokeLinecap="round" />
                </svg>
            </div>
            <div className="h2-new font-bold mt-[60px] ">Thank you!</div>
            <div className="p1-new text-gray-600 mt-2">Your form is successfully submitted.</div>
            {/*<div className="p1 mt-4 text-black-800">We hold your privacy in high regard</div>*/}
            {form?.settings?.requireVerifiedIdentity && form?.settings?.allowEditingResponse && (
                <ActiveLink className="mt-1 font-normal !text-blue-500 cursor-pointer" href="/">
                    {' '}
                    Edit your response
                </ActiveLink>
            )}
            {!auth.id && showSubmissionNumber && (
                <div className="mt-14 mb-10 max-w-[360px]">
                    <div
                        className="p2-new p-3 bg-new-white-200 rounded border-[1px] border-black-200 flex gap-4  text-new-black-700 cursor-pointer"
                        onClick={() => {
                            copyToClipboard(submissionNumber || '');
                            toast('Copied', { type: 'info' });
                        }}
                    >
                        <span>{submissionNumber || ''}</span>
                        <span>
                            <CopyIcon className="text-new-black-600" />
                        </span>
                    </div>
                    <div className="text-black-600 !text-center mt-2 p2-new">
                        Use this submission number to view or to request deletion of this response.
                        <ActiveLink className="text-blue-500 ml-1 cursor-pointer" href={workspaceResponseUrl}>
                            Go my response
                        </ActiveLink>
                    </div>
                </div>
            )}
            <div
                className={`px-3 py-2 flex gap-2  ${isDisabled ? 'cursor-default' : 'cursor-pointer'} mt-10 bg-white items-center rounded-md border-gray-200 border-[2px]`}
                onClick={() => {
                    if (!isDisabled) {
                        router.push('https://bettercollected.com');
                    }
                }}
            >
                <SmallLogo className="w-6 h-6" />
                <span className="body3 text-black-700">Try bettercollected</span>
            </div>
        </div>
    );
}
