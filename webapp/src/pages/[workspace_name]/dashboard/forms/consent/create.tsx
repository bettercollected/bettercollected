import React from 'react';

import BackButtonMenuBar from '@Components/Common/BackButtonMenuBar';
import AttentionText from '@Components/Consent/AttentionText';
import ConsentBuilder from '@Components/Consent/Builder/ConsentBuilder';
import ConsentInformationPanel from '@Components/Consent/ConsentInformationPanel';

import Layout from '@app/layouts/_layout';

export default function CreateConsent() {
    return (
        <div className="flex min-w-screen bg-white">
            <BackButtonMenuBar text="Back to Form" />
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
