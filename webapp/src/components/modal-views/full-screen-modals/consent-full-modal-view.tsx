import React, { useEffect } from 'react';

import BackButtonMenuBar from '@Components/Common/BackButtonMenuBar';
import AttentionText from '@Components/Consent/AttentionText';
import ConsentInformationPanel from '@Components/Consent/ConsentInformationPanel';
import ConsentForm from '@Components/Consent/Form/ConsentForm';
import HintBox from '@Components/Consent/Form/HintBox';

import { StandardFormDto } from '@app/models/dtos/form';

import { useFullScreenModal } from '../full-screen-modal-context';

interface ConsentFullModalProps {
    onFormSubmit: any;
    form: StandardFormDto;
}
export default function ConsentFullModalView() {
    const { closeModal, modalProps } = useFullScreenModal();
    const typedModalProps = modalProps as ConsentFullModalProps | null;

    return (
        <div className="flex w-full min-h-screen !bg-white">
            <BackButtonMenuBar text="Back to Form" onBack={closeModal} />
            <div className="mt-12">
                <div className="mx-[15px] sm:mx-[40px] md:ml-[120px] xl:ml-[267px] w-fit md:w-[508px] mt-6">
                    <HintBox title="Your data is not submitted yet" description="We outline how your data will be used. Review these terms before submitting any information." />
                    <AttentionText className="mt-12" text={`Your data, your control. We value your privacy.`} />
                    <ConsentForm className="mt-10 pb-20 " onFormSubmit={typedModalProps?.onFormSubmit} form={typedModalProps?.form!} />
                </div>
            </div>
            <ConsentInformationPanel />
        </div>
    );
}
