import React, { useState } from 'react';

import cn from 'classnames';

import { Hint } from '@app/components/icons/hint';
import { useModal } from '@app/components/modal-views/context';
import { ConsentPurposeModalMode } from '@app/components/modal-views/modals/consent-purpose-modal-view';
import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { OnlyClassNameInterface } from '@app/models/interfaces';

import AutoCompleteInput from '../../Common/Input/AutoCompleteInput';

interface ConsentAddInputProps extends OnlyClassNameInterface {
    title?: string;
    placeholder?: string;
    hint?: string;
    options: string[];
    category: ConsentCategoryType;
    consentType: ConsentType;
}

export default function ConsentAddInput({ className, title, placeholder = '', hint, options, category, consentType }: ConsentAddInputProps) {
    const { openModal } = useModal();

    const handleSelect = (selection: string, mode: ConsentPurposeModalMode = 'add') => {
        console.log(selection);
        openModal('CONSENT_PURPOSE_MODAL_VIEW', { category, selection, type: consentType, mode });
    };
    return (
        <div className={cn('rounded-lg p-5 bg-new-black-200', className)}>
            {hint && (
                <div className="mb-4 relative">
                    <Hint className="absolute" />
                    <div className="ml-10 p2 !text-new-black-800 !xs:text-xs">{hint}</div>
                </div>
            )}
            <AutoCompleteInput dropdownTitle="Purpose Of The Form" title={title} placeholder={placeholder} className="!cursor-pointer" options={options} onSelect={handleSelect} />
        </div>
    );
}
