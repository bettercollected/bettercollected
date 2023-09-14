import React, { useState } from 'react';

import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import ConsentModalTopBar from '@Components/Consent/ConsentModalTopBar';
import ErrorText from '@Components/Consent/ErrorText';
import HintBox from '@Components/Consent/Form/HintBox';
import TermsAndCondition from '@Components/Consent/TermsAndCondition';

import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';
import useForm from '@app/lib/hooks/use-form';
import { ConsentCategoryType } from '@app/models/enums/consentEnum';
import { resetConsentState } from '@app/store/consent/actions';
import { selectConsentState } from '@app/store/consent/selectors';
import { IConsentAnswer, IConsentField } from '@app/store/consent/types';
import { resetFillForm } from '@app/store/fill-form/slice';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePublishFormMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import { useModal } from '../context';
import { useFullScreenModal } from '../full-screen-modal-context';

export default function ConsentBuilderConfirmationModalView() {
    const router = useRouter();
    const { error, setError } = useForm();
    const [formPurposeTermChecked, setFormPurposeTermChecked] = useState(true);
    const [publishForm, { isLoading }] = usePublishFormMutation();
    const builderState = useAppSelector(selectBuilderState);
    const workspace = useAppSelector(selectWorkspace);

    const handleFormPurposeTermChange = (checked: boolean) => {
        setFormPurposeTermChecked(checked);
    };
    const formPurposeTermsAndConditionDetails = (
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
        try {
            const response: any = await publishForm({ workspaceId: workspace.id, formId: builderState.id });
            if (response.data) {
                router.push(`/${workspace.workspaceName}/dashboard/forms/${builderState.id}`);
            }
        } catch (error) {}
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
                {formPurposeTermsAndConditionDetails}
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
