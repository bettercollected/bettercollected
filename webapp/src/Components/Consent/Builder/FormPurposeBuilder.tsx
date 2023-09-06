import React from 'react';

import { useModal } from '@app/components/modal-views/context';
import { ConsentPurposeModalMode, ConsentPurposeModalProps } from '@app/components/modal-views/modals/consent-purpose-modal-view';
import { dataRetention, formPurpose } from '@app/data/consent';
import { StandardFormDto } from '@app/models/dtos/form';
import { ConsentCategoryType } from '@app/models/enums/consentEnum';
import { IConsentOption } from '@app/models/types/consentTypes';

import ConsentAddInput from './ConsentAddInput';
import ConsentBuilderFieldList from './ConsentBuilderFieldList';

interface FormPurposeBuilderProps {
    form?: StandardFormDto;
    isPreview: boolean;
    options: IConsentOption[];
}
export default function FormPurposeBuilder({ form, isPreview, options }: FormPurposeBuilderProps) {
    const { openModal } = useModal();

    const handleSelect = (selection: IConsentOption, mode: ConsentPurposeModalMode = 'add') => {
        const modalProps: ConsentPurposeModalProps = { consent: selection, mode };
        openModal('CONSENT_PURPOSE_MODAL_VIEW', modalProps);
    };
    // const isFormPurposeAvailable = form?.consent.filter((consent) => consent.category === ConsentCategoryType.PurposeOfTheForm).length !== 0;
    // if (isFormPurposeAvailable) {
    return (
        <div>
            <div className="h4-new pb-5 xs:pb-[17px]">Purpose Of This Form:</div>
            <ConsentBuilderFieldList isPreview={isPreview} category={ConsentCategoryType.PurposeOfTheForm} />
            {!isPreview && (
                <ConsentAddInput className="mt-5 xs:mt-[17px]" title={formPurpose.title} placeholder="Select or Add Purpose" hint={formPurpose.hint} options={options} dropdownTitle="Purpose Of The Form" showCreateNewOptionButton onSelect={handleSelect} />
            )}
        </div>
    );
    // }
}
