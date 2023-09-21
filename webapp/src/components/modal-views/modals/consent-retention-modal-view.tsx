import React, { useEffect, useRef, useState } from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import ConsentInput from '@Components/Consent/Builder/ConsentInput';
import ConsentModalTopBar from '@Components/Consent/ConsentModalTopBar';
import TermsAndCondition from '@Components/Consent/TermsAndCondition';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';

import { ConsentCategoryType, ConsentType, ResponseRetentionType } from '@app/models/enums/consentEnum';
import { setAddConsent, setResponseRetention } from '@app/store/consent/actions';
import { IConsentField } from '@app/store/consent/types';
import { useAppDispatch } from '@app/store/hooks';

import { useModal } from '../context';

export interface ConsentRetentionModalProps {
    type: ResponseRetentionType;
}

export default function ConsentRetentionModalView({ type }: ConsentRetentionModalProps) {
    const [isChecked, setIsChecked] = useState(false);
    const [days, setDays] = useState<string>();
    const [date, setDate] = useState<string>();
    const { closeModal } = useModal();

    const ref = useRef<HTMLInputElement>(null);

    const dispatch = useAppDispatch();
    const handleDayChange = (event: any) => {
        setDays(event.target.value.toString());
    };
    const handleDateChange = (event: any) => {
        setDate(event.target.value);
    };
    useEffect(() => {
        const blockEscape = (event: KeyboardEvent) => {
            if (event.key == 'Escape') {
                event.stopPropagation();
            }
        };
        document.addEventListener('keydown', blockEscape);
        return () => {
            document.removeEventListener('keydown', blockEscape);
        };
    }, []);

    const handleSubmit = (event: any) => {
        event.preventDefault();
        const isDaysInValid = type === 'days' && (days === undefined || days === '');
        const isDateInValid = type === 'date' && (date === undefined || date === '');
        if (!isChecked || isDaysInValid || isDateInValid) return;

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
            dispatch(setResponseRetention({ expiration: days, expirationType: 'days' }));
        } else if (type === 'date') {
            consentField.title = `Until ${date}`;
            consentField.description = `Your data will be deleted after ${date}`;
            dispatch(setResponseRetention({ expiration: date, expirationType: 'date' }));
        }
        dispatch(setAddConsent(consentField));
        closeModal();
    };

    const renderInputComponent = () => {
        if (type === 'days') {
            return <ConsentInput ref={ref} type="number" autoFocus showIcon={false} title="For how many days you want to store user data" placeholder="Enter number of days" onChange={handleDayChange} InputProps={{ inputProps: { min: 1 } }} />;
        }
        return (
            <ConsentInput
                autoFocus
                ref={ref}
                type="date"
                title="Choose a specific date until which data will be retained"
                placeholder="Select date"
                onChange={handleDateChange}
                InputProps={{ inputProps: { min: new Date(new Date().getTime() + 24 * 60 * 60 * 1000).toISOString().slice(0, 10) } }}
            />
        );
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
                    selected={isChecked}
                    className=""
                >
                    {`I understand that responders data will be automatically deleted after ${type === 'days' ? days + ' days.' : date}`}
                </TermsAndCondition>
                <AppButton type="submit" className="py-3 px-8 !bg-new-blue-500 md:w-[192px]">
                    Done
                </AppButton>
            </div>
        </form>
    );
}
