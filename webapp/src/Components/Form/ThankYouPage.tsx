import React from 'react';

import Image from 'next/legacy/image';
import { useRouter } from 'next/navigation';

import CopyIcon from '@Components/Common/Icons/Common/Copy';
import SmallLogo from '@Components/Common/Icons/Common/SmallLogo';
import { toast } from 'react-toastify';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { selectAuth } from '@app/store/auth/slice';
import { selectAnonymize } from '@app/store/fill-form/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getFullNameFromUser } from '@app/utils/userUtils';

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

    const anonymize = useAppSelector(selectAnonymize);

    const workspaceResponseUrl = isCustomDomain ? '/?view=my-submissions' : `/${workspace.workspaceName}?view=my-submissions`;

    return (
        <div className="flex h-full w-full flex-col items-center justify-start text-center">
            <div className="aspect-banner-mobile lg:aspect-thank_you_cover  relative  flex w-full items-center justify-center">
                <Image src="/images/thankyou_cover.png" layout="fill" objectFit="fill" alt="ALternative" />
                <svg
                    className="h-16 w-16 md:h-20 md:w-20 lg:h-24 lg:w-24"
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
            <div>
                <div className="h2-new mt-10 !text-left font-bold ">Thank you!</div>
                <div className="p2-new text-black-600 mt-1 !text-left">Your form is successfully submitted {auth.id && anonymize && 'anonymously'}.</div>
                {auth.id && !anonymize && (
                    <div className="bg-new-white-200 mt-6 flex w-fit gap-2 rounded p-2">
                        <AuthAccountProfileImage size={36} image={auth?.profileImage} name={getFullNameFromUser(auth) ?? ''} />
                        <div className="!text-black-700 flex flex-col justify-center gap-2 pr-1 text-start">
                            <span className="body6 !leading-none">{getFullNameFromUser(auth)?.trim() || auth?.email || ''}</span>
                            <span className="body5 !leading-none">{auth?.email} </span>
                        </div>
                    </div>
                )}

                {showSubmissionNumber && (
                    <div className="mb-10 mt-14 max-w-[360px]">
                        <div className="text-black-600  mb-2 !text-left text-xs italic">Store somewhere safe</div>
                        <div
                            className="p2-new bg-new-white-200 border-black-200 text-new-black-700 flex cursor-pointer gap-4 rounded  border-[1px] p-3"
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
                        <div className="text-black-700 p2-new mt-2 flex flex-wrap text-left">
                            <span>Use this submission number to view or request deletion of this response. </span>
                            <span>
                                <ActiveLink className="ml-1 cursor-pointer text-blue-500" href={workspaceResponseUrl}>
                                    See all your submissions
                                </ActiveLink>
                            </span>
                        </div>
                    </div>
                )}

                {!showSubmissionNumber && (
                    <div className="text-black-600 p2-new my-12 flex max-w-[360px] flex-wrap text-left">
                        You can view or request deletion of this response{' '}
                        <span>
                            <ActiveLink className="ml-1 cursor-pointer text-blue-500" href={workspaceResponseUrl}>
                                See all your submissions
                            </ActiveLink>
                        </span>
                    </div>
                )}
                <div>
                    <div className="text-black-700 mb-2 mt-10 text-left text-xs">Want to create privacy friendly forms?</div>
                    <div
                        className={`flex gap-2 px-3 py-2  ${isDisabled ? 'cursor-default' : 'cursor-pointer'} border-black-200 w-fit items-center rounded-md border-[1px] bg-white`}
                        onClick={() => {
                            if (!isDisabled) {
                                router.push('https://bettercollected.com');
                            }
                        }}
                    >
                        <SmallLogo className="h-6 w-6" />
                        <span className="p2-new text-black-700">Try bettercollected</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
