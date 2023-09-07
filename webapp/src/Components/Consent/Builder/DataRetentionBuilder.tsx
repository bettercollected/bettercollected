import React from 'react';

import { useModal } from '@app/components/modal-views/context';
import { ConsentRetentionModalProps } from '@app/components/modal-views/modals/consent-retention-modal-view';
import { dataRetention } from '@app/data/consent';
import { StandardFormDto } from '@app/models/dtos/form';
import { ConsentCategoryType } from '@app/models/enums/consentEnum';
import { IConsentOption } from '@app/models/types/consentTypes';
import { selectConsentState } from '@app/store/consent/selectors';
import { IConsentField } from '@app/store/consent/types';
import { useAppSelector } from '@app/store/hooks';

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

    const handleSelect = (selection: IConsentOption) => {
        const selectionIndex = options.indexOf(selection);
        if (selectionIndex === 0) {
            const modalProps: ConsentRetentionModalProps = { type: 'days' };
            openModal('CONSENT_RETENTION_MODAL_VIEW', modalProps);
        } else if (selectionIndex === 1) {
            const modalProps: ConsentRetentionModalProps = { type: 'date' };
            openModal('CONSENT_RETENTION_MODAL_VIEW', modalProps);
        } else {
        }
    };

    const isDataRetentionAvailable = form?.consent.filter((consent) => consent.category === ConsentCategoryType.DataRetention).length !== 0;
    if (!isDataRetentionAvailable) return <></>;
    return (
        <div>
            <div className="h4-new pb-5 xs:pb-[17px]">For How Long Data Will Be Stored</div>
            {consents?.map((consent, idx) => (
                <ConsentBuilderField key={consent.consentId} disabled={isPreview || consent.consentId === 'consent_data_collection'} className={`${idx === 0 && 'border-y'}`} consent={consent} />
            ))}
            {!isPreview && consents.length === 0 && (
                <ConsentAddInput className="mt-5 xs:mt-[17px]" title={dataRetention.title} placeholder="Select a Data Retention options" hint={dataRetention.hint} options={options} dropdownTitle="Data Retention Options" onSelect={handleSelect} />
            )}
        </div>
    );
}
