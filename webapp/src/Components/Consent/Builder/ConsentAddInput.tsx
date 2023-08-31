import React, { useRef, useState } from 'react';

import cn from 'classnames';

import { Hint } from '@app/components/icons/hint';
import { useModal } from '@app/components/modal-views/context';
import { ConsentPurposeModalMode, ConsentPurposeModalProps } from '@app/components/modal-views/modals/consent-purpose-modal-view';
import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { OnlyClassNameInterface } from '@app/models/interfaces';
import { IConsentOption } from '@app/models/types/consentTypes';

import ConsentAutoCompleteInput from '../ConsentAutoCompleteInput';

interface ConsentAddInputProps extends OnlyClassNameInterface {
    title?: string;
    placeholder?: string;
    hint?: string;
    options: IConsentOption[];
    category: ConsentCategoryType;
    consentType: ConsentType;
}

export default function ConsentAddInput({ className, title, placeholder = '', hint, options, category, consentType }: ConsentAddInputProps) {
    const { openModal } = useModal();

    const handleSelect = (selection: IConsentOption, mode: ConsentPurposeModalMode = 'add') => {
        const modalProps: ConsentPurposeModalProps = { consent: selection, mode };
        openModal('CONSENT_PURPOSE_MODAL_VIEW', modalProps);
    };
    return (
        <div className={cn('rounded-lg p-5 bg-new-black-200', className)}>
            {hint && (
                <div className="mb-4 relative">
                    <Hint className="absolute" />
                    <div className="ml-10 p2 !text-new-black-800">{hint}</div>
                </div>
            )}
            <ConsentAutoCompleteInput dropdownTitle="Purpose Of The Form" title={title} placeholder={placeholder} className="!cursor-pointer" options={options} onSelect={handleSelect} />
        </div>
    );
}
