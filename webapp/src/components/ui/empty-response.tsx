import React from 'react';

import { useTranslation } from 'next-i18next';

import Inbox from '@app/components/icons/inbox';

interface IEmptyResponseProps {
    title: string;
    description: string;
}
export default function EmptyResponse({ title, description }: IEmptyResponseProps) {
    const { t } = useTranslation();
    return (
        <div className="mt-[108px] flex flex-col items-center">
            <Inbox className="h-[48px] w-[48px]" />
            <p className="body1 text-black-900 mt-8 !leading-none text-center">{t(title)}</p>
            <p className="body4  text-black-700 mt-4 text-center">{t(description)}</p>
        </div>
    );
}
