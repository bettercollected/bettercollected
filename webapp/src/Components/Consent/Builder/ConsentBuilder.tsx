import React, { useState } from 'react';

import FormButton from '@Components/Common/Input/Button/FormButton';
import CheckBox from '@Components/Common/Input/CheckBox';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import cn from 'classnames';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { formPurpose } from '@app/data/consent';
import { StandardFormDto } from '@app/models/dtos/form';
import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { OnlyClassNameInterface } from '@app/models/interfaces';
import { IConsentOption } from '@app/models/types/consentTypes';
import { resetConsentState, setAddConsent, setPrivacyPolicy, setResponderRights } from '@app/store/consent/actions';
import { useGetAllWorkspaceConsentsQuery } from '@app/store/consent/api';
import { selectConsentState } from '@app/store/consent/selectors';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { validateConsentBuilder } from '@app/utils/validations/consent/consentBuilderValidation';

import ErrorText from '../ErrorText';
import ConsentAddInput from './ConsentAddInput';
import ConsentBuilderField from './ConsentBuilderField';
import ConsentInput from './ConsentInput';

interface ConsentBuilderProps extends OnlyClassNameInterface {
    onFormPublish?: any;
    isPreview?: boolean;
    form?: StandardFormDto;
}

export default function ConsentBuilder({ className, onFormPublish, isPreview = false, form }: ConsentBuilderProps) {
    const consentState = useAppSelector(selectConsentState);
    const workspace = useAppSelector(selectWorkspace);
    const { data } = useGetAllWorkspaceConsentsQuery(workspace.id);
    const [isDeletionRequestChecked, setIsDeletionRequestChecked] = useState(true);
    const dispatch = useAppDispatch();
    const { closeModal } = useFullScreenModal();
    const { openModal } = useModal();
    const [error, setError] = useState(false);

    const getFilteredConsents = (category: ConsentCategoryType) => {
        if (isPreview) {
            return form?.consent.map((consent, idx) => consent?.category === category && <ConsentBuilderField key={consent.consentId} disabled={isPreview} className={`${idx === 0 && 'border-y'}`} consent={consent} />);
        }
        return consentState.consents.map((consent, idx) => consent?.category === category && <ConsentBuilderField key={consent.consentId} className={`${idx === 0 && 'border-y'}`} consent={consent} />);
    };
    const getConsentOptions = () => {
        return [
            ...(data !== undefined
                ? data.map(
                      (consent) =>
                          ({
                              ...consent,
                              consentId: '',
                              isRecentlyAdded: true
                          } as IConsentOption)
                  )
                : []),
            ...formPurpose.options
        ];
    };
    const renderFormPurposes = () => {
        const formPurposes = form?.consent.filter((consent) => consent.category === ConsentCategoryType.PurposeOfTheForm).length !== 0;
        if (formPurposes) {
            return (
                <div>
                    <div className="h4-new pb-5 xs:pb-[17px]">Purpose Of This Form:</div>
                    {getFilteredConsents(formPurpose.category)}
                    {!isPreview && (
                        <ConsentAddInput
                            className="mt-5 xs:mt-[17px]"
                            title={formPurpose.title}
                            placeholder="Select or Add Purpose"
                            hint={formPurpose.hint}
                            options={getConsentOptions()}
                            category={ConsentCategoryType.PurposeOfTheForm}
                            consentType={ConsentType.Checkbox}
                        />
                    )}
                </div>
            );
        }
    };

    const responderRightDetails = (
        <>
            <div className="space-y-5">
                <div className="space-y-5">
                    <div className="h4-new">{`Responder's Rights`}</div>
                    <div className="flex space-x-2">
                        <CheckBox
                            id="responder-rights"
                            disabled={isPreview}
                            checked={isDeletionRequestChecked}
                            onChange={(event, checked) => {
                                setIsDeletionRequestChecked(checked);
                            }}
                        />
                        <div className="space-y-2">
                            <label htmlFor="responder-rights" className="h6-new cursor-pointer">
                                Request deletion of their data
                            </label>
                            <p className="p2">This field allows you to specify whether you will allow users to request the deletion of their data and other actions.</p>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );

    const onSubmit = async (event: any) => {
        event.preventDefault();
        if (isPreview) return;

        if (validateConsentBuilder(consentState)) {
            setError(false);
            const responderRightsConsentField = {
                consentId: uuidv4(),
                type: ConsentType.Info,
                category: ConsentCategoryType.RespondersRights,
                title: 'Responder Rights'
            };
            openModal('CONSENT_BUILDER_CONFIRMATION_MODAL_VIEW', {
                onFormPublish,
                consents: [...consentState.consents, isDeletionRequestChecked && responderRightsConsentField],
                privacyPolicyUrl: consentState.privacy_policy
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
                    <div className="p2 !text-new-black-800">
                        {`We want to make sure you're fully informed about how your data will be used before you proceed with our form. Our commitment to transparency means that we've included a consent page to provide you with important details. Here's what you
        can find on the consent page:`}
                    </div>
                </div>
                {renderFormPurposes()}
                {responderRightDetails}
                <div>
                    <div className="h4-new">Privacy Policy</div>
                    <ConsentInput
                        type="file"
                        disabled={isPreview}
                        title="Insert link to your privacy policy"
                        required
                        placeholder={isPreview ? form?.settings?.privacyPolicyUrl : 'Insert link here'}
                        className="mt-5"
                        onChange={(event: any) => {
                            dispatch(setPrivacyPolicy(event.target.value));
                        }}
                    />
                </div>
            </div>
            {!isPreview && (
                <div className="mt-[60px] space-y-3">
                    {error && <ErrorText text=" Please fill to all required consents." />}
                    <FormButton className="w-[192px]">Done</FormButton>
                </div>
            )}
        </form>
    );
}
