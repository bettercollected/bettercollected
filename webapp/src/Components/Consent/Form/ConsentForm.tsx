import React, { useState } from 'react';

import FormButton from '@Components/Common/Input/Button/FormButton';
import CheckBox from '@Components/Common/Input/CheckBox';
import cn from 'classnames';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { formPurpose } from '@app/data/consent';
import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { OnlyClassNameInterface } from '@app/models/interfaces';
import { IConsentOption } from '@app/models/types/consentTypes';
import { setAddConsent, setPrivacyPoilicy, setResponderRights } from '@app/store/consent/actions';
import { useGetAllWorkspaceConsentsQuery } from '@app/store/consent/api';
import { selectConsentState } from '@app/store/consent/selectors';
import { selectForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

import ConsentField from './ConsentField';

interface ConsentBuilderProps extends OnlyClassNameInterface {
    onFormSubmit: any;
}

export default function ConsentForm({ className, onFormSubmit }: ConsentBuilderProps) {
    const formState = useAppSelector(selectForm);
    const dispatch = useAppDispatch();
    const { closeModal } = useFullScreenModal();

    const getFilteredConsents = (category: ConsentCategoryType) => {
        debugger;
        return formState.consent.map((consent, idx) => consent?.category === category && <ConsentField key={consent.consentId} className={`${idx === 0 && 'border-y'}`} consent={consent} />);
    };
    const formPurposeDetails = (
        <>
            <div>
                <div className="h4-new pb-5 xs:pb-[17px]">Purpose of this form:</div>
                {getFilteredConsents(formPurpose.category)}
            </div>
        </>
    );

    const responderRightDetails = (
        <>
            <div className="space-y-5">
                <div className="h4-new">{`YourRights`}</div>
                <div className="h6-new">You can request for deletion of your data at any time</div>
            </div>
        </>
    );

    const onSubmit = async (event: any) => {
        event.preventDefault();
        try {
            dispatch(setResponderRights());
            await onFormSubmit();
            closeModal();
        } catch (e) {}
    };
    return (
        <form className={cn(className)} onSubmit={onSubmit}>
            <div className="space-y-20 xs:space-y-[70px]">
                <div className="space-y-4">
                    <div className="h4">Form Purpose and Data Usage</div>
                    <div className="p2 !text-new-black-800 xs:!text-xs">
                        {`We want to make sure you're fully informed about how your data will be used
before you proceed with our form. Our commitment to transparency means
that we've included a consent page to provide you with important details.`}
                    </div>
                </div>
                {formPurposeDetails}
                {responderRightDetails}
            </div>
            <FormButton className="w-[192px] mt-[60px]">Done</FormButton>
        </form>
    );
}
