import React, { useEffect, useState } from 'react';

import FormButton from '@Components/Common/Input/Button/FormButton';
import CheckBox from '@Components/Common/Input/CheckBox';
import ErrorIcon from '@mui/icons-material/Error';
import cn from 'classnames';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { formPurpose } from '@app/data/consent';
import { StandardFormDto } from '@app/models/dtos/form';
import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { OnlyClassNameInterface } from '@app/models/interfaces';
import { IConsentOption } from '@app/models/types/consentTypes';
import { setAddConsent, setPrivacyPolicy, setResponderRights } from '@app/store/consent/actions';
import { useGetAllWorkspaceConsentsQuery } from '@app/store/consent/api';
import { consent } from '@app/store/consent/consentSlice';
import { selectConsentState } from '@app/store/consent/selectors';
import { selectConsentAnswers } from '@app/store/fill-form/selectors';
import { resetFillForm } from '@app/store/fill-form/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { validateConsents } from '@app/utils/validations/consent/consentValidation';

import ConsentField from './ConsentField';

interface ConsentBuilderProps extends OnlyClassNameInterface {
    onFormSubmit: any;
    form: StandardFormDto;
    isPreview?: boolean;
}

export default function ConsentForm({ className, onFormSubmit, form, isPreview = false }: ConsentBuilderProps) {
    const { openModal } = useModal();
    const workspace = useAppSelector(selectWorkspace);
    const { data } = useGetWorkspaceMembersQuery({ workspaceId: workspace.id });
    const consentAnswers = useAppSelector(selectConsentAnswers);
    const [error, setError] = useState(false);

    const getFilteredConsents = (category: ConsentCategoryType) => {
        return form.consent.map((consent, idx) => consent?.category === category && <ConsentField key={consent.consentId} className={`${idx === 0 && 'border-y'}`} consent={consent} disabled={isPreview} />);
    };

    const dataAccessDetails = (
        <>
            <div className="space-y-5">
                <div className="h4-new">{`Who can access your data?`}</div>
                <div className="border-y border-new-black-300 py-5 space-y-2">
                    <div className="h6-new">
                        {workspace.workspaceName} with {data?.length} members
                    </div>
                    <ul className="space-y-3 list-disc !px-5">
                        <li className="p2">We will only collect and use your data as described in privacy policy.</li>
                        <li className="p2">We will not sell or share your data with any other third parties without your consent.</li>
                        <li className="p2">We will take all reasonable steps to protect your data from unauthorized access, use, or disclosure.</li>
                    </ul>
                </div>
            </div>
        </>
    );
    const renderResponderRights = () => {
        const responderRight = form.consent.filter((consent) => consent.category === ConsentCategoryType.RespondersRights).length !== 0;
        if (responderRight) {
            return (
                <div className="space-y-5">
                    <div className="h4-new">{`Your Rights`}</div>
                    <div className="h6-new border-y border-new-black-300 py-5">You can request for deletion of your data at any time</div>
                </div>
            );
        }
    };

    const renderFormPurposes = () => {
        const formPurposes = form.consent.filter((consent) => consent.category === ConsentCategoryType.PurposeOfTheForm).length !== 0;
        if (formPurposes) {
            return (
                <div>
                    <div className="h4-new pb-5">Purpose of this form:</div>
                    {getFilteredConsents(formPurpose.category)}
                </div>
            );
        }
    };
    const onSubmit = async (event: any) => {
        event.preventDefault();
        if (validateConsents(consentAnswers, form.consent)) {
            setError(false);
            openModal('CONSENT_CONFIRMATION_MODAL_VIEW', { onFormSubmit, consentAnswers, privacyPolicyUrl: form?.settings?.privacyPolicyUrl });
        } else {
            setError(true);
        }
    };

    return (
        <form className={cn(className)} onSubmit={onSubmit}>
            <div className="space-y-20 xs:space-y-[70px]">
                <div className="space-y-4">
                    <div className="h4">Form Purpose and Data Usage</div>
                    <div className="p2 !text-new-black-800 ">
                        {`We want to make sure you're fully informed about how your data will be used
before you proceed with our form. Our commitment to transparency means
that we've included a consent page to provide you with important details.`}
                    </div>
                </div>
                {renderFormPurposes()}
                {renderResponderRights()}
                {dataAccessDetails}
            </div>
            {!isPreview && (
                <div className="mt-[60px] space-y-3">
                    {error && (
                        <div className="p2 !text-new-pink items-center !font-normal">
                            <span className="mr-2">
                                <ErrorIcon />
                            </span>
                            Please agree to all required consents.
                        </div>
                    )}
                    <FormButton className="w-[192px]">Done</FormButton>
                </div>
            )}
        </form>
    );
}
