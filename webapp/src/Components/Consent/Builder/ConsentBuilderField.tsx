import React from 'react';

import CheckBox from '@Components/Common/Input/CheckBox';
import cn from 'classnames';

import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';
import { ConsentCategoryType } from '@app/models/enums/consentEnum';
import { OnlyClassNameInterface } from '@app/models/interfaces';
import { setRemoveConsent } from '@app/store/consent/actions';
import { IConsentField } from '@app/store/consent/types';
import { useAppDispatch } from '@app/store/hooks';

interface ConsentBuilderFieldProps extends OnlyClassNameInterface {
    disabled?: boolean;
    consent: IConsentField;
    onClick?: (consent: IConsentField) => void;
    hint?: string;
    onRemoveCallback?: () => void;
}

export default function ConsentBuilderField({ consent, className, hint, disabled = false, onClick, onRemoveCallback }: ConsentBuilderFieldProps) {
    const dispatch = useAppDispatch();

    const handleRemoveConsent = (event: any) => {
        event.stopPropagation();
        if (disabled) return;
        onRemoveCallback && onRemoveCallback();
        dispatch(setRemoveConsent(consent.consentId));
    };

    if (consent.category === ConsentCategoryType.DataRetention) {
        return (
            <div className="space-y-3">
                <div id={`item-${consent.consentId}`} className={cn('flex items-center justify-between space-y-2 p-5 rounded-lg  bg-new-black-200 group', className, disabled && 'hover:cursor-default')}>
                    <div className="h6-new">{consent.title}</div>
                    <DropdownCloseIcon className={cn('!m-0 hover:cursor-pointer', disabled && 'hidden')} onClick={handleRemoveConsent} />
                </div>
                {consent.title !== 'Forever' && hint && hint !== '' && <p className="p2 !text-new-pink">{hint}</p>}
            </div>
        );
    }
    return (
        <div
            id={`item-${consent.consentId}`}
            className={cn('space-y-2 p-5 border-b border-new-black-300 hover:bg-new-black-200 hover:cursor-pointer group', className, disabled && 'hover:cursor-default hover:!bg-white')}
            onClick={() => {
                if (disabled) return;
                onClick && onClick(consent);
            }}
        >
            <div className="flex items-center justify-between">
                <div className="flex space-x-2 ">
                    {consent.type === 'checkbox' && <CheckBox disabled defaultChecked={disabled} className="!m-0" />}
                    <div className="h6-new">
                        {consent.title} {consent.required && <span className="ml-2 text-new-pink">*</span>}
                    </div>
                </div>
                <DropdownCloseIcon className={cn('!m-0 hidden group-hover:block', disabled && 'group-hover:hidden')} onClick={handleRemoveConsent} />
            </div>

            {consent.description !== '' && (
                <div className="space-y-2">
                    <p className="p2">{consent.description}</p>
                </div>
            )}
        </div>
    );
}
