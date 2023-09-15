import React, { useEffect } from 'react';

import BackButtonMenuBar from '@Components/Common/BackButtonMenuBar';
import AttentionText from '@Components/Consent/AttentionText';
import ConsentBuilder from '@Components/Consent/Builder/ConsentBuilder';
import ConsentInformationPanel from '@Components/Consent/ConsentInformationPanel';
import ConsentForm from '@Components/Consent/Form/ConsentForm';
import HintBox from '@Components/Consent/Form/HintBox';

import { StandardFormDto } from '@app/models/dtos/form';

import { useFullScreenModal } from '../full-screen-modal-context';

interface ConsentFullModalProps {
    onFormSubmit: any;
    form: StandardFormDto;
    isPreview?: boolean;
}
export default function ConsentFullModalView({ onFormSubmit, form, isPreview = false }: ConsentFullModalProps) {
    const { closeModal } = useFullScreenModal();

    return (
        <div className="flex flex-col w-full min-h-screen !bg-white max-h-screen overflow-auto">
            <div className="absolute top-0 left-0 w-full bg-white z-[100] ">
                <BackButtonMenuBar text="Back to Form" onBack={closeModal} />
            </div>
            <div className="mt-12">
                <div className="mx-[15px] sm:mx-[40px] md:ml-[120px] xl:ml-[267px] w-fit md:w-[508px] mt-6">
                    {!isPreview && (
                        <>
                            <HintBox title="Your data is not submitted yet" description="We outline how your data will be used. Review these terms before submitting any information." />
                            <AttentionText className="mt-12" text={`Your data, your control. We value your privacy.`} />
                        </>
                    )}
                    <ConsentForm className="mt-10 pb-20 " onFormSubmit={onFormSubmit} form={form!} isPreview={isPreview} />
                </div>
            </div>
            {!isPreview && <ConsentInformationPanel />}
        </div>
    );
}
