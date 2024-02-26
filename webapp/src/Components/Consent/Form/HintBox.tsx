import React from 'react';

import cn from 'classnames';

import { Hint } from '@app/components/icons/hint';
import { OnlyClassNameInterface } from '@app/models/interfaces';


type HintBoxSize = 'small' | 'normal';

interface HintBoxProps extends OnlyClassNameInterface {
    title: string;
    description?: string;
    size?: HintBoxSize;
    iconColor?: string;
    linkText?: string;
    onLinkClick?: any;
}

export default function HintBox({ title, description, className, size = 'normal', iconColor = '#FFA716', onLinkClick, linkText }: HintBoxProps) {
    const titleClassName = size === 'small' && 'leading-6 font-semibold';
    return (
        <div className={cn('rounded-lg p-5 bg-new-black-200', className)}>
            <div className="relative">
                <Hint className="absolute" fillColor={iconColor} />
                <div className="ml-10">
                    <div className={cn('h4-new', titleClassName)}>{title}</div>
                    <div className="p2 !text-new-black-800 mt-3">{description}</div>
                    {linkText && (
                        <div className="p2 !text-new-blue-500 mt-4 cursor-pointer" onClick={onLinkClick}>
                            {linkText}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}