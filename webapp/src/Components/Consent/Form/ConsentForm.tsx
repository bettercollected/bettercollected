import React, { useState } from 'react';

import FormButton from '@Components/Common/Input/Button/FormButton';
import ErrorIcon from '@mui/icons-material/Error';
import cn from 'classnames';

import { useModal } from '@app/components/modal-views/context';
import { dataRetention, formPurpose } from '@app/data/consent';
import { StandardFormDto } from '@app/models/dtos/form';
import { ConsentCategoryType } from '@app/models/enums/consentEnum';
import { OnlyClassNameInterface } from '@app/models/interfaces';
import { selectConsentAnswers } from '@app/store/fill-form/selectors';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { validateConsents } from '@app/utils/validations/consent/consentValidation';

import ConsentField from './ConsentField';

interface ConsentBuilderProps extends OnlyClassNameInterface {
    onFormSubmit: any;
    form: StandardFormDto;
    isDisabled?: boolean;
}

export default function ConsentForm({ className, onFormSubmit, form, isDisabled = false }: ConsentBuilderProps) {
    const { openModal } = useModal();
    const workspace = useAppSelector(selectWorkspace);
    const { data } = useGetWorkspaceMembersQuery({ workspaceId: workspace.id });
    const consentAnswers = useAppSelector(selectConsentAnswers);
    const [error, setError] = useState(false);

    const getFilteredConsents = (category: ConsentCategoryType) => {
        return form?.consent?.filter((consent) => consent?.category === category).map((consent, idx) => <ConsentField key={consent.consentId} className={`${idx === 0 && 'border-y'}`} consent={consent} disabled={isDisabled} />);
    };

    const dataAccessDetails = (
        <>
            <div className="space-y-5">
                <div className="h3-new">{`Who Can Access Your Data?`}</div>
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
        const responderRight = form?.consent?.filter((consent) => consent.category === ConsentCategoryType.RespondersRights).length !== 0;
        if (responderRight) {
            return (
                <div className="space-y-5">
                    <div className="h3-new">{`Your Rights`}</div>
                    <div className="h5-newborder-y border-new-black-300 py-5">You can request for deletion of your data at any time</div>
                </div>
            );
        }
    };

    const renderFormPurposes = () => {
        const formPurposes = form?.consent?.filter((consent) => consent.category === ConsentCategoryType.PurposeOfTheForm).length !== 0;
        if (formPurposes) {
            return (
                <div>
                    <div className="h3-new pb-5">Purpose of this form:</div>
                    {getFilteredConsents(formPurpose.category)}
                </div>
            );
        }
    };
    const renderDataRetention = () => {
        const isDataRetentionAvailable = form?.consent?.filter((consent) => consent.category === ConsentCategoryType.DataRetention).length !== 0;
        if (isDataRetentionAvailable) {
            return (
                <div>
                    <div className="h3-new pb-5">For How Long Data Will Be Stored</div>
                    {getFilteredConsents(dataRetention.category)}
                </div>
            );
        }
    };
    const onSubmit = async (event: any) => {
        event.preventDefault();
        if (validateConsents(consentAnswers, form.consent)) {
            setError(false);
            openModal('CONSENT_CONFIRMATION_MODAL_VIEW', {
                onFormSubmit,
                consentAnswers,
                privacyPolicyUrl: form?.settings?.privacyPolicyUrl
            });
        } else {
            setError(true);
        }
    };

    return (
        <form className={cn(className)} onSubmit={onSubmit}>
            <div className="space-y-20 xs:space-y-[70px]">
                <div className="space-y-4">
                    <div className="h4">Form Purpose and Data Usage</div>
                    <div className="p2 !text-new-black-800 ">{`We want to make sure you're fully informed about how your data will be used before you proceed with our form.`}</div>
                </div>
                {renderFormPurposes()}
                {renderDataRetention()}
                {renderResponderRights()}
                {dataAccessDetails}
            </div>
            {!isDisabled && (
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
