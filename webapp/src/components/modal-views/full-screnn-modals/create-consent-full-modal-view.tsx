import React from 'react';

import BackButtonMenuBar from '@Components/Common/BackButtonMenuBar';
import AttentionText from '@Components/Consent/AttentionText';
import ConsentBuilder from '@Components/Consent/Builder/ConsentBuilder';
import ConsentInformationPanel from '@Components/Consent/ConsentInformationPanel';

import { useFullScreenModal } from '../full-screen-modal-context';

export default function CreateConsentFullModalView() {
    const { closeModal } = useFullScreenModal();
    return (
        <div className="flex w-full !bg-white">
            <BackButtonMenuBar text="Back to Form" onBack={closeModal} />
            <div className="mt-12">
                <div className="mx-[15px] sm:mx-[40px] md:ml-[120px] xl:ml-[267px] w-fit md:w-[508px] mt-6">
                    <AttentionText className="mt-12" text={`Design your form responder's consent page`} />
                    <ConsentBuilder className="mt-10 pb-20" />
                </div>
            </div>
            <ConsentInformationPanel />
        </div>
    );
}
