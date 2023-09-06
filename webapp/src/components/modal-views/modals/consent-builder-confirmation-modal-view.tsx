import React, { useState } from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import ConsentModalTopBar from '@Components/Consent/ConsentModalTopBar';
import ErrorText from '@Components/Consent/ErrorText';
import HintBox from '@Components/Consent/Form/HintBox';
import TermsAndCondition from '@Components/Consent/TermsAndCondition';

import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';
import useForm from '@app/lib/hooks/use-form';
import { ConsentCategoryType } from '@app/models/enums/consentEnum';
import { resetConsentState } from '@app/store/consent/actions';
import { IConsentAnswer, IConsentField } from '@app/store/consent/types';
import { resetFillForm } from '@app/store/fill-form/slice';
import { useAppDispatch } from '@app/store/hooks';

import { useModal } from '../context';
import { useFullScreenModal } from '../full-screen-modal-context';

export interface ConsentBuilderConfirmationModalProps {
    onFormPublish: any;
    consents: IConsentField[];
    privacyPolicyUrl: string;
}

export default function ConsentBuilderConfirmationModaView({ onFormPublish, consents, privacyPolicyUrl }: ConsentBuilderConfirmationModalProps) {
    const { closeModal } = useModal();
    const fullScreenModal = useFullScreenModal();
    const dispatch = useAppDispatch();
    const { isLoading, error, setError, setLoading } = useForm();
    const [formPurposeTermChecked, setFormPurposeTermChecked] = useState(true);

    const handleFormPurposeTermChange = (checked: boolean) => {
        setFormPurposeTermChecked(checked);
    };
    const formPurposeTermsAndConditonDetails = (
        <TermsAndCondition onAgree={handleFormPurposeTermChange} className="border-b border-new-black-300 p-5">
            <TermsAndCondition.Title>{`I have mentioned all the form's purposes.`}</TermsAndCondition.Title>
            <TermsAndCondition.Description>{`This confirms that you have clearly mentioned all the purposes for which data is being collected in your forms.`}</TermsAndCondition.Description>
        </TermsAndCondition>
    );

    const onSubmit = async (event: any) => {
        event.preventDefault();

        if (!formPurposeTermChecked) {
            setError(true);
            return;
        }
        setLoading(true);
        try {
            await onFormPublish(consents, privacyPolicyUrl);
            closeModal();
            fullScreenModal.closeModal();
            dispatch(resetConsentState());
        } catch (error) {
        } finally {
            setLoading(false);
        }
    };
    return (
        <form onSubmit={onSubmit} className="bg-white rounded-2xl w-fit md:w-[476px] h-content">
            <ConsentModalTopBar />
            <div className="pt-5 px-6">
                <HintBox
                    size="small"
                    iconColor="#FE3678"
                    title={`You care about your Responders' data`}
                    description={`Make sure you have clearly mentioned all the purposes for which data is being collected in your form, as well as all third-party apps integrated with your platform.`}
                />
                {formPurposeTermsAndConditonDetails}
            </div>
            <div className="p-10">
                {error && <ErrorText text="Please accept all terms and conditions before proceeding." />}
                <AppButton isLoading={isLoading} type="submit" className="bg-new-blue-500 !w-full !py-3">
                    Confirm & Publish
                </AppButton>
            </div>
        </form>
    );
}
