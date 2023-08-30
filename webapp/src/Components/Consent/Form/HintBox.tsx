import React from 'react';

import { extend } from 'lodash';

import cn from 'classnames';

import { Hint } from '@app/components/icons/hint';
import { OnlyClassNameInterface } from '@app/models/interfaces';

interface HintBoxProps extends OnlyClassNameInterface {
    title: string;
    description?: string;
}
export default function HintBox({ title, description, className }: HintBoxProps) {
    return (
        <div className={cn('rounded-lg p-5 bg-new-black-200', className)}>
            <div className="relative">
                <Hint className="absolute" fillColor="#FFA716" />
                <div className="ml-10 space-y-3">
                    <div className="h5-new">{title}</div>
                    <div className="p2 !text-new-black-800">{description}</div>
                </div>
            </div>
        </div>
    );
}
