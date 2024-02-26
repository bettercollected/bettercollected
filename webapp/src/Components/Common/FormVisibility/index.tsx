import React from 'react';

import { useTranslation } from 'next-i18next';

import PrivateIcon from '@Components/Common/Icons/Form/Private';
import PublicIcon from '@Components/Common/Icons/Form/Public';

import { localesCommon } from '@app/constants/locales/common';


interface IFormVisibilityProps {
    isPrivate: boolean;
    size?: 'small' | 'medium';
}

FormVisibility.defaultProps = {
    size: 'small'
};

export default function FormVisibility({ isPrivate, size }: IFormVisibilityProps) {
    const { t } = useTranslation();

    const dimensions = size === 'small' ? 12 : 16;

    const Icon = isPrivate ? PrivateIcon : PublicIcon;

    return (
        <div className="flex items-center">
            <Icon height={dimensions} width={dimensions} />
            <p className={`leading-none ${size === 'small' ? 'text-[12px]' : 'text-[14px]'}  text-black-900 ml-2`}>{isPrivate ? t(localesCommon.hidden) : t(localesCommon.public)}</p>
        </div>
    );
}