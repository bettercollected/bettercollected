import React from 'react';

import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';

import { useModal } from '@app/components/modal-views/context';
import { ConsentRetentionModalProps } from '@app/components/modal-views/modals/consent-retention-modal-view';
import { dataRetention } from '@app/data/consent';
import { StandardFormDto } from '@app/models/dtos/form';
import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { IConsentOption } from '@app/models/types/consentTypes';
import { resetResponseRetention, setAddConsent, setResponseRetention } from '@app/store/consent/actions';
import { selectConsentState } from '@app/store/consent/selectors';
import { IConsentField } from '@app/store/consent/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

import ConsentAddInput from './ConsentAddInput';
import ConsentBuilderField from './ConsentBuilderField';

interface DataRetentionBuilderProps {
    form?: StandardFormDto;
    isPreview: boolean;
    consents: IConsentField[];
    options: IConsentOption[];
}
export default function DataRetentionBuilder({ form, isPreview, options, consents }: DataRetentionBuilderProps) {
    const { openModal } = useModal();
    const consentState = useAppSelector(selectConsentState);
    const dispatch = useAppDispatch();

    const handleSelect = (selection: IConsentOption) => {
        const selectionIndex = options.indexOf(selection);
        if (selectionIndex === 0) {
            const modalProps: ConsentRetentionModalProps = { type: 'days' };
            openModal('CONSENT_RETENTION_MODAL_VIEW', modalProps);
        } else if (selectionIndex === 1) {
            const modalProps: ConsentRetentionModalProps = { type: 'date' };
            openModal('CONSENT_RETENTION_MODAL_VIEW', modalProps);
        } else {
            dispatch(
                setAddConsent({
                    consentId: uuidv4(),
                    category: ConsentCategoryType.DataRetention,
                    description: '',
                    type: ConsentType.Info,
                    title: 'Forever'
                })
            );
        }
    };

    const isDataRetentionAvailable = form?.consent.filter((consent) => consent.category === ConsentCategoryType.DataRetention).length !== 0;
    if (!isDataRetentionAvailable) return <></>;
    return (
        <div>
            <div className="h3-new pb-5 xs:pb-[17px]">For How Long Data Will Be Stored?</div>
            {consents?.map((consent, idx) => (
                <ConsentBuilderField
                    key={consent.consentId}
                    disabled={isPreview}
                    className={`${idx === 0 && 'border-y'}`}
                    consent={consent}
                    onRemoveCallback={() => {
                        resetResponseRetention();
                    }}
                    hint={consentState.responseExpirationType === 'forever' ? '' : `Responders data will be automatically deleted after ${consentState.responseExpiration} ${consentState.responseExpirationType === 'days' && ' days.'}`}
                />
            ))}
            {!isPreview && consents.length === 0 && (
                <ConsentAddInput className="mt-5 xs:mt-[17px]" title={dataRetention.title} placeholder="Select a Data Retention options" hint={dataRetention.hint} options={options} dropdownTitle="Data Retention Options" onSelect={handleSelect} />
            )}
        </div>
    );
}
