import React, { useEffect, useState } from 'react';

import CheckBox from '@Components/Common/Input/CheckBox';
import cn from 'classnames';

import { OnlyClassNameInterface } from '@app/models/interfaces';
import { setUpdateConsent } from '@app/store/consent/actions';
import { IConsentAnswer, IConsentField } from '@app/store/consent/types';
import { selectConsentAnswers } from '@app/store/fill-form/selectors';
import { addConsentAnswer, selectAnswer } from '@app/store/fill-form/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

interface ConsentFieldProps extends OnlyClassNameInterface {
    consent: IConsentAnswer;
    disabled?: boolean;
}
export default function ConsentField({ consent, className, disabled = false }: ConsentFieldProps) {
    const dispatch = useAppDispatch();
    const [isChecked, setIsChecked] = useState(consent.accepted ?? false);

    const handleCheckSelection = (event: any, checked: boolean) => {
        setIsChecked(checked);
        dispatch(addConsentAnswer({ ...consent, accepted: checked }));
    };

    useEffect(() => {
        if (disabled) return;
        dispatch(addConsentAnswer(consent));
    }, []);
    return (
        <div className={cn('space-y-2 p-5 border-b border-new-black-300', className)}>
            <div className="flex space-x-2 items-center">
                {consent.type === 'checkbox' && <CheckBox className="!m-0" checked={isChecked} disabled={disabled} onChange={handleCheckSelection} />}
                <div className="h6-new">
                    {consent.title} {consent.required && <span className="ml-2 text-new-pink">*</span>}
                </div>
            </div>

            {consent.description !== '' && (
                <div className="space-y-2">
                    <p className="p2">{consent.description}</p>
                </div>
            )}
        </div>
    );
}
