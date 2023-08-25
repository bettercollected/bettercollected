import React from 'react';

import cn from 'classnames';

import { Hint } from '@app/components/icons/hint';
import { OnlyClassNameInterface } from '@app/models/interfaces';

import ConsentInput from './ConsentInput';

interface ConsentAddInputProps extends OnlyClassNameInterface {
    title: string;
    placeholder: string;
    hint?: string;
}

export default function ConsentAddInput({ className, title, placeholder, hint }: ConsentAddInputProps) {
    return (
        <div className={cn('rounded-lg p-5 bg-new-black-200', className)}>
            {hint && (
                <div className="mb-4 relative">
                    <Hint className="absolute" />
                    <div className="ml-10 p2 !text-new-black-800">{hint}</div>
                </div>
            )}
            <ConsentInput placeholder={placeholder} className="!cursor-pointer" />
        </div>
    );
}
