import React from 'react';

import { Autocomplete } from '@mui/material';
import cn from 'classnames';

import { Hint } from '@app/components/icons/hint';
import { OnlyClassNameInterface } from '@app/models/interfaces';

import ConsentInput from '../Common/Input/AutoCompleteInput';
import AutoCompleteInput from '../Common/Input/AutoCompleteInput';

interface ConsentAddInputProps extends OnlyClassNameInterface {
    title?: string;
    placeholder?: string;
    hint?: string;
    options: string[];
}

export default function ConsentAddInput({ className, title, placeholder = '', hint, options }: ConsentAddInputProps) {
    return (
        <div className={cn('rounded-lg p-5 bg-new-black-200', className)}>
            {hint && (
                <div className="mb-4 relative">
                    <Hint className="absolute" />
                    <div className="ml-10 p2 !text-new-black-800">{hint}</div>
                </div>
            )}
            <AutoCompleteInput title={title} placeholder={placeholder} className="!cursor-pointer" options={options} />
        </div>
    );
}
