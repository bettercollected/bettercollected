import React from 'react';

import { useTranslation } from 'next-i18next';

import { Typography } from '@mui/material';

import AnchorLink from '../ui/links/anchor-link';


interface ISettingCard {
    title: string;
    description: string;
    link: string;
}

export default function SettingCard({ title, description, link }: ISettingCard) {
    const { t } = useTranslation();

    return (
        <div className="p-6 bg-white md:w-[740px]">
            <p className="sh3">{title}</p>
            <p className="mt-4 mb-6 body4 !text-black-700">{description}</p>
            <div className="flex gap-[22px] items-center">
                <Typography className="body4 !text-brand-500" noWrap>
                    <AnchorLink href={link} target="_blank">
                        {link}
                    </AnchorLink>
                </Typography>
            </div>
        </div>
    );
}