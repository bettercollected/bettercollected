import React, { useState } from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import ConsentInput from '@Components/Consent/Builder/ConsentInput';
import ConsentModalTopBar from '@Components/Consent/ConsentModalTopBar';
import TermsAndCondition from '@Components/Consent/TermsAndCondition';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';

import { ConsentCategoryType, ConsentType, RetentionType } from '@app/models/enums/consentEnum';
import { setAddConsent } from '@app/store/consent/actions';
import { IConsentField } from '@app/store/consent/types';
import { useAppDispatch } from '@app/store/hooks';

import { useModal } from '../context';

export interface ConsentRetentionModalProps {
    type: RetentionType;
}
export default function ConsentRetentionModalView({ type }: ConsentRetentionModalProps) {
    const [isChecked, setIsChecked] = useState(false);
    const [days, setDays] = useState<number | null>(null);
    const [date, setDate] = useState<string | null>(null);
    const { closeModal } = useModal();

    const dispatch = useAppDispatch();
    const handleDayChange = (event: any) => {
        setDays(event.target.value);
    };
    const handleDateChange = (event: any) => {
        setDate(event.target.value);
    };

    const handleSubmit = (event: any) => {
        event.preventDefault();
        if (!isChecked) return;

        let consentField: IConsentField = {
            consentId: uuidv4(),
            category: ConsentCategoryType.DataRetention,
            description: '',
            type: ConsentType.Info,
            title: ''
        };
        if (type === 'days') {
            consentField.title = `For ${days} days`;
            consentField.description = `Your data will be deleted after ${days} days`;
        } else if (type === 'date') {
            consentField.title = `For ${date}`;
            consentField.description = `Your data will be deleted after ${date}`;
        } else {
            consentField.title = `Forever`;
            consentField.description = `Your data will stay forever`;
        }

        dispatch(setAddConsent(consentField));
        closeModal();
    };

    const renderInputComponent = () => {
        if (type === 'days') {
            return <ConsentInput type="number" showIcon={false} title="For how many days you want to store user data" placeholder="Enter number of days" onChange={handleDayChange} />;
        }
        return <ConsentInput type="date" title="Choose a specific date until which data will be retained" placeholder="Select date" onChange={handleDateChange} />;
    };

    return (
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl w-fit md:w-[621px] h-content">
            <ConsentModalTopBar />
            <div className="px-7 md:px-10 py-4 md:py-6 space-y-6 md:space-y-8">
                {renderInputComponent()}
                <TermsAndCondition
                    type="normal"
                    onAgree={(checked) => {
                        setIsChecked(checked);
                    }}
                    selected={false}
                    className=""
                >
                    {`I understand that responders data will be automatically deleted after
[customizable time period].`}
                </TermsAndCondition>
                <AppButton type="submit" className="py-3 px-8 !bg-new-blue-500 md:w-[192px]">
                    Done
                </AppButton>
            </div>
        </form>
    );
}
