import React, { useState } from 'react';

import CheckBox from '@Components/Common/Input/CheckBox';
import cn from 'classnames';

import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';
import { useModal } from '@app/components/modal-views/context';
import { ConsentPurposeModalProps } from '@app/components/modal-views/modals/consent-purpose-modal-view';
import { OnlyClassNameInterface } from '@app/models/interfaces';
import { setRemoveConsent } from '@app/store/consent/actions';
import { consent } from '@app/store/consent/consentSlice';
import { IConsentField, IConsentState } from '@app/store/consent/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

type ConsentType = 'info' | 'checkbox';

interface ConsentBuilderFieldProps extends OnlyClassNameInterface {
    consent: IConsentField;
}
export default function ConsentBuilderField({ consent, className }: ConsentBuilderFieldProps) {
    const dispatch = useAppDispatch();
    const { openModal } = useModal();

    const handleRemoveConsent = (event: any) => {
        event.stopPropagation();
        dispatch(setRemoveConsent(consent.consentId));
    };
    const handleModalOpen = () => {
        const modalProps: ConsentPurposeModalProps = { consent, mode: 'update' };
        openModal('CONSENT_PURPOSE_MODAL_VIEW', modalProps);
    };

    return (
        <div id={`item-${consent.consentId}`} className={cn('space-y-2 p-5 border-b border-new-black-300 hover:bg-new-black-200 hover:cursor-pointer group', className)} onClick={handleModalOpen}>
            <div className="flex items-center justify-between">
                <div className="flex space-x-2 ">
                    {consent.type === 'checkbox' && <CheckBox disabled className="!m-0" />}
                    <div className="h6-new">
                        {consent.title} {consent.required && <span className="ml-2 text-new-pink">*</span>}
                    </div>
                </div>

                <DropdownCloseIcon className="hidden group-hover:block" onClick={handleRemoveConsent} />
            </div>

            {consent.description !== '' && (
                <div className="space-y-2">
                    <p className="p2">{consent.description}</p>
                </div>
            )}
        </div>
    );
}
