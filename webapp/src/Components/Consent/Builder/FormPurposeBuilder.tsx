import React from 'react';

import { useModal } from '@app/components/modal-views/context';
import { ConsentPurposeModalMode, ConsentPurposeModalProps } from '@app/components/modal-views/modals/consent-purpose-modal-view';
import { dataRetention, formPurpose } from '@app/data/consent';
import { StandardFormDto } from '@app/models/dtos/form';
import { ConsentCategoryType } from '@app/models/enums/consentEnum';
import { IConsentOption } from '@app/models/types/consentTypes';
import { selectConsentState } from '@app/store/consent/selectors';
import { IConsentField } from '@app/store/consent/types';
import { useAppSelector } from '@app/store/hooks';

import ConsentAddInput from './ConsentAddInput';
import ConsentBuilderField from './ConsentBuilderField';

interface FormPurposeBuilderProps {
    form?: StandardFormDto;
    isPreview: boolean;
    options: IConsentOption[];
    consents: IConsentField[];
}
export default function FormPurposeBuilder({ form, isPreview, options, consents }: FormPurposeBuilderProps) {
    const { openModal } = useModal();

    const handleModalOpen = (consent: IConsentField) => {
        const modalProps: ConsentPurposeModalProps = { consent, mode: 'update' };
        openModal('CONSENT_PURPOSE_MODAL_VIEW', modalProps);
    };

    const handleSelect = (selection: IConsentOption, mode: ConsentPurposeModalMode = 'add') => {
        const modalProps: ConsentPurposeModalProps = { consent: selection, mode };
        openModal('CONSENT_PURPOSE_MODAL_VIEW', modalProps);
    };

    const isFormPurposeAvailable = form?.consent.filter((consent) => consent.category === ConsentCategoryType.PurposeOfTheForm).length !== 0;
    if (!isFormPurposeAvailable) return <></>;

    return (
        <div>
            <div className="h4-new pb-5 xs:pb-[17px]">Purpose Of This Form:</div>
            {consents?.map((consent, idx) => (
                <ConsentBuilderField key={consent.consentId} disabled={isPreview || consent.consentId === 'consent_data_collection'} className={`${idx === 0 && 'border-y'}`} consent={consent} onClick={handleModalOpen} />
            ))}
            {!isPreview && (
                <ConsentAddInput className="mt-5 xs:mt-[17px]" title={formPurpose.title} placeholder="Select or Add Purpose" hint={formPurpose.hint} options={options} dropdownTitle="Purpose Of The Form" showCreateNewOptionButton onSelect={handleSelect} />
            )}
        </div>
    );
}
