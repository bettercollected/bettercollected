import React from 'react';

import { extend } from 'lodash';

import cn from 'classnames';

import { Hint } from '@app/components/icons/hint';
import { OnlyClassNameInterface } from '@app/models/interfaces';

type HintBoxSize = 'small' | 'normal';

interface HintBoxProps extends OnlyClassNameInterface {
    title: string;
    description?: string;
    size?: HintBoxSize;
    iconColor?: string;
}
export default function HintBox({ title, description, className, size = 'normal', iconColor = '#FFA716' }: HintBoxProps) {
    const titleClassName = size === 'small' && 'leading-6 font-semibold';
    return (
        <div className={cn('rounded-lg p-5 bg-new-black-200', className)}>
            <div className="relative">
                <Hint className="absolute" fillColor={iconColor} />
                <div className="ml-10 space-y-3">
                    <div className={cn('h5-new', titleClassName)}>{title}</div>
                    <div className="p2 !text-new-black-800">{description}</div>
                </div>
            </div>
        </div>
    );
}
