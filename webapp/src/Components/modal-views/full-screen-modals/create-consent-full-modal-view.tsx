import React from 'react';

import BackButtonMenuBar from '@Components/Common/BackButtonMenuBar';
import AttentionText from '@Components/Consent/AttentionText';
import ConsentBuilder from '@Components/Consent/Builder/ConsentBuilder';
import ConsentInformationPanel from '@Components/Consent/ConsentInformationPanel';
import cn from 'classnames';

import { Close } from '@app/Components/icons/close';
import { StandardFormDto } from '@app/models/dtos/form';

import { useFullScreenModal } from '../full-screen-modal-context';


interface CreateConsentFullModalProps {
    form?: StandardFormDto;
    isPreview?: boolean;
}

export default function CreateConsentFullModalView({ form, isPreview = false }: CreateConsentFullModalProps) {
    const { closeModal } = useFullScreenModal();
    return (
        <div className={cn('flex flex-col w-full min-h-screen !bg-white  overflow-auto', isPreview && '!bg-transparent pt-40')}>
            {!isPreview && (
                <div className="absolute top-0 left-0 w-full bg-white z-[100] ">
                    <BackButtonMenuBar text="Back to Form" onBack={closeModal} />
                </div>
            )}
            {isPreview && (
                <div className="bg-white w-16 h-16 fixed top-20 z-[3000] right-10 shadow-lg rounded-full flex items-center justify-center cursor-pointer" onClick={closeModal}>
                    <Close width="32px" height="40px" stroke="#4D4D4D" strokeWidth={0.8} />
                </div>
            )}
            <div className={cn('mt-12 w-full bg-white min-h-screen', isPreview && 'rounded-t-3xl !mt-0 !pt-12 overflow-y-auto scroll-mt-6')}>
                <div className="mx-[15px] sm:mx-[40px] md:ml-[120px] xl:ml-[267px] w-fit md:w-[508px] mt-6">
                    {!isPreview && <AttentionText className="mt-12" text={`Design your form responder's consent page`} />}
                    <ConsentBuilder className="mt-10 pb-20" isPreview={isPreview} form={form} />
                </div>
            </div>
            {!isPreview && <ConsentInformationPanel />}
        </div>
    );
}