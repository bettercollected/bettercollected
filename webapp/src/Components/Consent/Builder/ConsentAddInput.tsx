import React from 'react';

import cn from 'classnames';

import { Hint } from '@app/components/icons/hint';
import { ConsentPurposeModalMode } from '@app/components/modal-views/modals/consent-purpose-modal-view';
import { OnlyClassNameInterface } from '@app/models/interfaces';
import { IConsentOption } from '@app/models/types/consentTypes';

import ConsentAutoCompleteInput from '../ConsentAutoCompleteInput';

interface ConsentAddInputProps extends OnlyClassNameInterface {
    title?: string;
    placeholder?: string;
    hint?: string;
    options: IConsentOption[];
    dropdownTitle: string;
    showCreateNewOptionButton?: boolean;
    onSelect?: (selection: IConsentOption, mode?: ConsentPurposeModalMode) => void;
}

export default function ConsentAddInput({ className, hint, ...inputOptions }: ConsentAddInputProps) {
    return (
        <div className={cn('rounded-lg p-5 bg-new-black-200', className)}>
            {hint && (
                <div className="mb-4 relative">
                    <Hint className="absolute" />
                    <div className="ml-10 p2 !text-new-black-800">{hint}</div>
                </div>
            )}
            <ConsentAutoCompleteInput className="!cursor-pointer" {...inputOptions} />
        </div>
    );
}
