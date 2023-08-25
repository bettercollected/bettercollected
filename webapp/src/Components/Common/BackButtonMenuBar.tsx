import React from 'react';

import { ArrowBack } from '@app/components/icons/arrow-back';

interface BackButtonMenuBarProps {
    text: string;
}
export default function BackButtonMenuBar({ text }: BackButtonMenuBarProps) {
    return (
        <div className="flex py-2 px-5 items-center w-full fixed">
            <div className="flex items-center space-x-1 cursor-pointer">
                <ArrowBack />
                <p className="p2">{text}</p>
            </div>
        </div>
    );
}
