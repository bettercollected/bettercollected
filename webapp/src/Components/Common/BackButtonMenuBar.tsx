import React from 'react';

import { ArrowBack } from '@app/components/icons/arrow-back';

interface BackButtonMenuBarProps {
    text: string;
    onBack?: () => void;
}
export default function BackButtonMenuBar({ text, onBack }: BackButtonMenuBarProps) {
    return (
        <div className="flex px-5 items-center w-full fixed h-12 bg-white ">
            <div className="flex items-center space-x-1 cursor-pointer" onClick={onBack}>
                <ArrowBack />
                <p className="p2 hidden md:block">{text}</p>
            </div>
        </div>
    );
}
