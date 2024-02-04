import React, { useState } from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import GreenShield from '@Components/Common/Icons/Common/GreenShield';
import InfoIcon from '@Components/Common/Icons/FormBuilder/infoIcon';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import ErrorText from '@Components/Consent/ErrorText';
import TermsAndCondition from '@Components/Consent/TermsAndCondition';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';

import AnchorLink from '@app/components/ui/links/anchor-link';
import useForm from '@app/lib/hooks/use-form';
import { ConsentCategoryType } from '@app/models/enums/consentEnum';
import { selectAuth } from '@app/store/auth/slice';
import { IConsentAnswer } from '@app/store/consent/types';
import { selectAnonymize, setAnonymize } from '@app/store/fill-form/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

import { useModal } from '../context';

export interface ConsentConfirmationModalProps {
    onFormSubmit: any;
    consentAnswers: Record<string, IConsentAnswer>;
    privacyPolicyUrl?: string;
}

export default function ConsentConfirmationModalView({ onFormSubmit, consentAnswers, privacyPolicyUrl }: ConsentConfirmationModalProps) {
    const { closeModal } = useModal();
    const form = useAppSelector(selectForm);
    const auth = useAppSelector(selectAuth);
    const dispatch = useAppDispatch();
    const { isLoading, error, setError, setLoading } = useForm();
    const [formPurposeTermChecked, setFormPurposeTermChecked] = useState(true);
    const [privacyTermChecked, setPrivacyTermChecked] = useState(true);

    const anonymize = useAppSelector(selectAnonymize);
    const renderPurposeTermsAndCondition = () => {
        const formPurpose = Object.values(consentAnswers).filter((answer) => answer.category === ConsentCategoryType.PurposeOfTheForm).length !== 0;
        if (formPurpose) {
            return (
                <TermsAndCondition selected={formPurposeTermChecked} onAgree={(checked) => setFormPurposeTermChecked(checked)} className="mt-2">
                    <TermsAndCondition.Title> {`I have reviewed all the form's purposes.`}</TermsAndCondition.Title>
                    {/*<TermsAndCondition.Description>{`This confirms whether you've taken a moment to go through the stated intentions of the form before proceeding.`}</TermsAndCondition.Description>*/}
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
            await onFormSubmit(consentAnswers, anonymize);
            closeModal();
        } catch (e) {
        } finally {
            setLoading(false);
        }
    };
    return (
        <HeaderModalWrapper headerTitle="Confirm and Submit">
            <form onSubmit={onSubmit} className="!w-full flex flex-col items-center">
                <GreenShield />
                <div className="w-full">
                    <div className="h3-new mt-10">We care about your data privacy!</div>
                    <div className="text-black-700 mt-2 p2-new mb-6">After confirming and submitting, you acknowledge understanding and agree to the data usage terms.</div>
                    {renderPurposeTermsAndCondition()}
                    <TermsAndCondition selected={privacyTermChecked} onAgree={(checked) => setPrivacyTermChecked(checked)} className="mt-2">
                        <TermsAndCondition.Title>
                            I agree to the{' '}
                            <AnchorLink href={privacyPolicyUrl || ''} target="_blank" referrerPolicy="no-referrer" className="text-new-blue-500">
                                privacy policy
                            </AnchorLink>
                        </TermsAndCondition.Title>
                        {/*<TermsAndCondition.Description>{`By checking this box, you indicate your acceptance and understanding of the provided terms and conditions.`}</TermsAndCondition.Description>*/}
                    </TermsAndCondition>

                    <div className={`p2-new mt-4 h-4 text-black-600 ${auth?.id && !anonymize ? 'visible' : 'invisible'}`}> You are submitting this form as {auth?.email}</div>
                    {auth?.id && !form?.settings?.requireVerifiedIdentity && (
                        <TermsAndCondition
                            selected={anonymize}
                            onAgree={(checked) => {
                                dispatch(setAnonymize(checked));
                            }}
                            className="mt-2"
                        >
                            <TermsAndCondition.Title>
                                <div className="flex gap-2 items-center">
                                    <span className="p2-new">Hide your email form form collector.</span>
                                    <Tooltip title="Submit this form without revealing your email to the creator.">
                                        <InfoIcon width={18} height={18} color="black" className="cursor-pointer" />
                                    </Tooltip>
                                </div>
                            </TermsAndCondition.Title>
                        </TermsAndCondition>
                    )}
                    <div className="mt-6">
                        {error && <ErrorText text="Please accept all terms and conditions before proceeding." />}

                        <AppButton type="submit" isLoading={isLoading} size={ButtonSize.Medium} className="bg-new-blue-500 !w-full mt-2">
                            Confirm & Submit
                        </AppButton>
                    </div>
                </div>
            </form>
        </HeaderModalWrapper>
    );
}
