import React, {useEffect, useState} from 'react';

import {useRouter} from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import ConsentModalTopBar from '@Components/Consent/ConsentModalTopBar';
import ErrorText from '@Components/Consent/ErrorText';
import HintBox from '@Components/Consent/Form/HintBox';
import TermsAndCondition from '@Components/Consent/TermsAndCondition';
import useForm from '@app/lib/hooks/use-form';
import {selectBuilderState} from '@app/store/form-builder/selectors';
import {useAppSelector} from '@app/store/hooks';
import {usePublishFormMutation} from '@app/store/workspaces/api';
import {selectWorkspace} from '@app/store/workspaces/slice';

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
                <TermsAndCondition selected={formPurposeTermChecked} onAgree={handleFormPurposeTermChange} className="border-b border-new-black-300 p-5">
                    <TermsAndCondition.Title>{`I have mentioned all the form's purposes.`}</TermsAndCondition.Title>
                    <TermsAndCondition.Description>{`This confirms that you have clearly mentioned all the purposes for which data is being collected in your forms.`}</TermsAndCondition.Description>
                </TermsAndCondition>
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
