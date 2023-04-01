import React, { useRef } from 'react';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Settingsprivacy from '@app/components/settings/workspace/settings-privacy';

export default function UpdateTermsOfServiceAndPrivacyPolicy(props: any) {
    const { closeModal } = useModal();

    const ref = useRef<HTMLDivElement>(null);

    return (
        <div ref={ref} className="relative m-auto w-full items-start justify-between rounded-lg bg-white scale-110">
            <div className="relative flex flex-col items-center gap-8 justify-between p-10">
                <div className="py-6 px-3 max-w-xs text-center w-full">
                    <svg aria-hidden="true" className="mx-auto mb-4 text-gray-400 w-14 h-14 dark:text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <h3 className="mb-5 text-lg font-normal text-gray-500 dark:text-gray-400">Update your company&apos;s Terms of Service and Privacy Policy</h3>

                    <Settingsprivacy className="w-full lg:!w-full mb-0" childClassName="lg:!w-full" />
                </div>
            </div>
            <Close onClick={() => closeModal()} className="cursor-pointer absolute top-3 right-3 h-auto w-3 text-gray-600 hover:text-black dark:text-white" />
        </div>
    );
}
