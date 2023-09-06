import React from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import ConsentInput from '@Components/Consent/Builder/ConsentInput';
import ConsentModalTopBar from '@Components/Consent/ConsentModalTopBar';
import TermsAndCondition from '@Components/Consent/TermsAndCondition';

type RetentionType = 'days' | 'date';

export interface ConsentRetentionModalProps {
    type: RetentionType;
}
export default function ConsentRetentionModalView({ type }: ConsentRetentionModalProps) {
    const renderInputComponent = () => {
        if (type === 'days') {
            return <ConsentInput showIcon={false} title="For how many days you want to store user data" placeholder="Enter number of days" />;
        }
        return <ConsentInput type="date" title="Choose a specific date until which data will be retained" placeholder="Select date" />;
    };
    return (
        <div className="bg-white rounded-2xl w-fit md:w-[621px] h-content">
            <ConsentModalTopBar />
            <div className="px-7 md:px-10 py-4 md:py-6 space-y-6 md:space-y-8">
                {renderInputComponent()}
                <TermsAndCondition type="normal" onAgree={(checked) => {}} selected={false} className="">
                    {`I understand that responders data will be automatically deleted after
[customizable time period].`}
                </TermsAndCondition>
                <AppButton className="py-3 px-8 !bg-new-blue-500 md:w-[192px]">Done</AppButton>
            </div>
        </div>
    );
}
