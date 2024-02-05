import React from 'react';

import EmptyFormIcon from '@Components/Common/Icons/Form/EmptyForm';

interface IZeroElementProps {
    title: string;
    description: string;
    className?: string;
}

export default function ZeroElement({ title, description, className = '' }: IZeroElementProps) {
    return (
        <div className={`flex flex-col w-full h-full items-center justify-center min-h-[290px] text-center py-[60px] bg-white rounded-xl px-13 gap-4 ${className}`}>
            <EmptyFormIcon />
            <div>
                <h1 className="h4-new mt-2">{title}</h1>
                <p className="p2-new mt-1 max-w-[290px] md:max-w-[316px] !text-black-700">{description}</p>
            </div>
        </div>
    );
}
