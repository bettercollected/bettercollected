import React from 'react';

import { Button } from '@mui/material';

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
            <Button onClick={onClick} variant="outlined" className="body4 !leading-none !p-2 bg-white !text-brand-500 !border-blue-200 hover:!bg-brand-200 capitalize">
                {buttonText}
            </Button>
        </div>
    );
}