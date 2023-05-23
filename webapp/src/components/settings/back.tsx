import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Back from '@app/components/icons/back';
import { buttonConstant } from '@app/constants/locales/buttons';

export default function BackButton() {
    const router = useRouter();
    const { t } = useTranslation();

    const handleBackClick = async () => {
        await router.back();
    };
    return (
        <div className="paragraph text-black-900 cursor-pointer flex items-center gap-1 py-4 hover:text-brand-500 hover:underline" onClick={handleBackClick}>
            <Back />
            <span>{t(buttonConstant.back)}</span>
        </div>
    );
}
