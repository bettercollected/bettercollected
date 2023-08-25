import React from 'react';

import { Hint } from '@app/components/icons/hint';

import ConsentInput from './ConsentInput';

interface ConsentAddInputProps {
    title: string;
    placeholder: string;
    hint?: string;
}

export default function ConsentAddInput({ title, placeholder, hint }: ConsentAddInputProps) {
    return (
        <div className="rounded-lg p-5 bg-[#F6F6F6]">
            {hint && (
                <div className="mb-4 relative">
                    <Hint className="absolute" />
                    <div className="ml-10 p2 !text-new-black-800">{hint}</div>
                </div>
            )}
            <div className="space-y-3">
                <div className="h6">{title}</div>
                <ConsentInput placeholder={placeholder} className="!cursor-pointer" />
            </div>
        </div>
    );
}
