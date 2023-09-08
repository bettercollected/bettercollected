import React, { useState } from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import ConsentModalTopBar from '@Components/Consent/ConsentModalTopBar';
import ErrorText from '@Components/Consent/ErrorText';
import HintBox from '@Components/Consent/Form/HintBox';
import TermsAndCondition from '@Components/Consent/TermsAndCondition';

import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';
import AnchorLink from '@app/components/ui/links/anchor-link';
import useForm from '@app/lib/hooks/use-form';
import { ConsentCategoryType } from '@app/models/enums/consentEnum';
import { IConsentAnswer } from '@app/store/consent/types';
import { resetFillForm } from '@app/store/fill-form/slice';
import { useAppDispatch } from '@app/store/hooks';

import { useModal } from '../context';
import { useFullScreenModal } from '../full-screen-modal-context';

export interface ConsentConfirmationModalProps {
    onFormSubmit: any;
    consentAnswers: Record<string, IConsentAnswer>;
    privacyPolicyUrl?: string;
}

export default function ConsentConfirmationModaView({ onFormSubmit, consentAnswers, privacyPolicyUrl }: ConsentConfirmationModalProps) {
    const { closeModal } = useModal();
    const fullScreenModal = useFullScreenModal();
    const dispatch = useAppDispatch();
    const { isLoading, error, setError, setLoading } = useForm();
    const [formPurposeTermChecked, setFormPurposeTermChecked] = useState(true);
    const [privacyTermChecked, setPrivacyTermChecked] = useState(true);

    const renderPurposeTermsAndConditon = () => {
        const formPurpose = Object.values(consentAnswers).filter((answer) => answer.category === ConsentCategoryType.PurposeOfTheForm).length !== 0;
        if (formPurpose) {
            return (
                <TermsAndCondition onAgree={(checked) => setFormPurposeTermChecked(checked)} className="border-b border-new-black-300 p-5">
                    <TermsAndCondition.Title> {`I have reviewed all the form's purposes.`}</TermsAndCondition.Title>
                    <TermsAndCondition.Description>{`This confirms whether you've taken a moment to go through the stated intentions of the form before proceeding.`}</TermsAndCondition.Description>
                </TermsAndCondition>
            );
        }
    };
    const onSubmit = async (event: any) => {
        event.preventDefault();
        if (!formPurposeTermChecked && !privacyTermChecked) {
            setError(true);
            return;
        }
        setLoading(true);
        try {
            await onFormSubmit(consentAnswers);
            closeModal();
            fullScreenModal.closeModal();
            dispatch(resetFillForm());
        } catch (e) {
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
                    title={`Putting your data's safety first!`}
                    description={`This page ensures you've seen and understood the data usage you're granting. Your trust is essential, and we're here to protect your information.`}
                />
                {renderPurposeTermsAndConditon()}
                <TermsAndCondition onAgree={(checked) => setPrivacyTermChecked(checked)} className="border-b border-new-black-300 p-5">
                    <TermsAndCondition.Title>
                        I agree to the{' '}
                        <AnchorLink href={privacyPolicyUrl || ''} target="_blank" referrerPolicy="no-referrer" className="text-new-blue-500">
                            privacy policy
                        </AnchorLink>
                    </TermsAndCondition.Title>
                    <TermsAndCondition.Description>{`By checking this box, you indicate your acceptance and understanding of the provided terms and conditions.`}</TermsAndCondition.Description>
                </TermsAndCondition>
            </div>
            <div className="p-10">
                {error && <ErrorText text="Please accept all terms and conditions before proceeding." />}
                <AppButton type="submit" isLoading={isLoading} className="bg-new-blue-500 !w-full !py-3">
                    Confirm & Submit
                </AppButton>
            </div>
        </form>
    );
}
