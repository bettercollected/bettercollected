import React, { useState } from 'react';

import FormButton from '@Components/Common/Input/Button/FormButton';
import CheckBox from '@Components/Common/Input/CheckBox';
import cn from 'classnames';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { formPurpose } from '@app/data/consent';
import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { OnlyClassNameInterface } from '@app/models/interfaces';
import { IConsentOption } from '@app/models/types/consentTypes';
import { resetConsentState, setAddConsent, setPrivacyPoilicy, setResponderRights } from '@app/store/consent/actions';
import { useGetAllWorkspaceConsentsQuery } from '@app/store/consent/api';
import { selectConsentState } from '@app/store/consent/selectors';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

import ConsentAddInput from './ConsentAddInput';
import ConsentBuilderField from './ConsentBuilderField';
import ConsentInput from './ConsentInput';

interface ConsentBuilderProps extends OnlyClassNameInterface {
    onFormPublish: any;
}

export default function ConsentBuilder({ className, onFormPublish }: ConsentBuilderProps) {
    const consentState = useAppSelector(selectConsentState);
    const workspace = useAppSelector(selectWorkspace);
    const { data } = useGetAllWorkspaceConsentsQuery(workspace.id);
    const [isDeletionRequestChecked, setIsDeletionRequestChecked] = useState(true);
    const dispatch = useAppDispatch();
    const { closeModal } = useFullScreenModal();

    const getFilteredConsents = (category: ConsentCategoryType) => {
        return consentState.consents.map((consent, idx) => consent?.category === category && <ConsentBuilderField key={consent.consentId} className={`${idx === 0 && 'border-y'}`} consent={consent} />);
    };
    const getConsentOptions = () => {
        return [...(data !== undefined ? data.map((consent) => ({ ...consent, consentId: '', isRecentlyAdded: true } as IConsentOption)) : []), ...formPurpose.options];
    };
    const formPurposeDetails = (
        <>
            <div>
                <div className="h4-new pb-5 xs:pb-[17px]">Purpose of this form:</div>
                {getFilteredConsents(formPurpose.category)}
                <ConsentAddInput
                    className="mt-5 xs:mt-[17px]"
                    title={formPurpose.title}
                    placeholder="Select or Add Purpose"
                    hint={formPurpose.hint}
                    options={getConsentOptions()}
                    category={ConsentCategoryType.PurposeOfTheForm}
                    consentType={ConsentType.Checkbox}
                />
            </div>
        </>
    );

    const responderRightDetails = (
        <>
            <div className="space-y-5">
                <div className="space-y-5">
                    <div className="h4-new">{`Responder's Rights`}</div>
                    <div className="flex space-x-2">
                        <CheckBox
                            checked={isDeletionRequestChecked}
                            onChange={(event, checked) => {
                                setIsDeletionRequestChecked(checked);
                            }}
                        />
                        <div className="space-y-2">
                            <div className="h6-new">Request deletion of their data</div>
                            <p className="p2">This field allows you to specify whether you will allow users to request the deletion of their data and other actions.</p>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );

    const onSubmit = async (event: any) => {
        event.preventDefault();
        try {
            dispatch(setResponderRights());
            await onFormPublish(consentState.consents);
            dispatch(resetConsentState());
            closeModal();
        } catch (e) {}
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
                {formPurposeDetails}
                {responderRightDetails}
                <div>
                    <div className="h4-new">Privacy Policy</div>
                    <ConsentInput
                        type="file"
                        title="Insert Link to Your Terms And Conditions"
                        placeholder="Insert link here"
                        className="mt-5"
                        onChange={(event: any) => {
                            dispatch(setPrivacyPoilicy(event.target.value));
                        }}
                    />
                </div>
            </div>
            <FormButton className="w-[192px] mt-[60px]">Done</FormButton>
        </form>
    );
}
