import React from 'react';

import cn from 'classnames';

import { ArrowBack } from '@app/components/icons/arrow-back';

interface BackButtonMenuBarProps {
    text: string;
    className?: string;
    onBack?: () => void;
}
export default function BackButtonMenuBar({ text, onBack, className }: BackButtonMenuBarProps) {
    return (
        <div className={cn('flex px-5 items-center w-full h-12 bg-white', className)}>
            <div className="flex items-center space-x-1 cursor-pointer" onClick={onBack}>
                <ArrowBack />
                <p className="p2 hidden md:block">{text}</p>
            </div>
        </div>
    );
}
