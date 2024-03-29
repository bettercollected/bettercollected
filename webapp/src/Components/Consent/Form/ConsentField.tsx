import React, { useEffect, useState } from 'react';

import CheckBox from '@Components/Common/Input/CheckBox';
import cn from 'classnames';

import { OnlyClassNameInterface } from '@app/models/interfaces';
import { IConsentAnswer } from '@app/store/consent/types';
import { addConsentAnswer } from '@app/store/fill-form/slice';
import { useAppDispatch } from '@app/store/hooks';


interface ConsentFieldProps extends OnlyClassNameInterface {
    consent: IConsentAnswer;
    disabled?: boolean;
}

export default function ConsentField({ consent, className, disabled = false }: ConsentFieldProps) {
    const dispatch = useAppDispatch();
    const [isChecked, setIsChecked] = useState(consent.accepted ?? false);

    const handleCheckSelection = (event: any) => {
        setIsChecked(!isChecked);
        dispatch(addConsentAnswer({ ...consent, accepted: !isChecked }));
    };

    useEffect(() => {
        if (disabled) return;
        dispatch(addConsentAnswer(consent));
    }, []);
    return (
        <div className={cn('space-y-2 p-5 border-b border-new-black-300', className)}>
            <div className="flex space-x-2 items-center">
                {consent.type === 'checkbox' && <CheckBox id={consent.consentId} className="!m-0" checked={isChecked} disabled={disabled} onClick={handleCheckSelection} />}
                <label htmlFor={consent.consentId} className="h5-newcursor-pointer">
                    {consent.title} {consent.required && <span className="ml-2 text-new-pink">*</span>}
                </label>
            </div>

            {consent.description !== '' && (
                <div className="space-y-2">
                    <p className="p2">{consent.description}</p>
                </div>
            )}
        </div>
    );
}