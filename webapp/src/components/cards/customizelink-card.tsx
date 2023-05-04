import React from 'react';

import Button from '@app/components/ui/button/button';

interface ICustomizeLinkProps {
    title: string;
    subtitle: string;
    buttonText: string;
    onClick: () => void;
}

export default function CustomizeLink({ title, subtitle, buttonText, onClick }: ICustomizeLinkProps) {
    return (
        <div className="flex flex-col items-center  px-[21px] py-[24px] bg-brand-600 rounded-[8px]">
            <p className="sh3 !text-white text-center">{title}</p>
            <p className="body4 !text-brand-100 text-center pt-4 pb-6">{subtitle}</p>
            <Button variant="outline" size="extraSmall" onClick={onClick}>
                {buttonText}
            </Button>
        </div>
    );
}
