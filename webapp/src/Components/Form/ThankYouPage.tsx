import React from 'react';

import Image from 'next/image';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import SmallLogo from '@Components/Common/Icons/Common/SmallLogo';
import { toast } from 'react-toastify';

import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';

interface IThankYouPageProps {
    isDisabled?: boolean;
    showSubmissionNumber?: boolean;
    submissionNumber?: string;
}

ThankYouPage.defaultProps = {
    isDisabled: false
};

export default function ThankYouPage({ isDisabled, showSubmissionNumber, submissionNumber }: IThankYouPageProps) {
    const router = useRouter();

    const [_, copyToClipboard] = useCopyToClipboard();

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
            <div className="h2 font-bold mt-[60px] ">Thank you!</div>
            <div className="h4 text-gray-600 mt-4">Your form is successfully submitted.</div>
            <div className="p1 mt-4 text-black-800">We hold your privacy in high regard</div>
            {showSubmissionNumber && (
                <>
                    <div className="mt-10 text-black-500 p2-new">This submission number may be used to view this response or request for deletion of this particular response</div>
                    <div
                        className="h2-new mt-2 mb-10 text-new-black-800 cursor-pointer"
                        onClick={() => {
                            copyToClipboard(submissionNumber || '');
                            toast('Copied', { type: 'success' });
                        }}
                    >
                        <Tooltip title="Click to copied!">
                            <span>{submissionNumber || ''}</span>
                        </Tooltip>
                    </div>
                </>
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
