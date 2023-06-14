import React from 'react';

import { useTranslation } from 'next-i18next';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';

export default function FormSettings() {
    const { t } = useTranslation();
    return (
        <div className="md:max-w-[740px]">
            <p className="body1 !leading-none">{t(localesCommon.settings)}</p>
            <p className="sm:max-w-[301px] body4 mt-4 mb-8 !text-black-700">{t(formConstant.settings.description)}</p>
            <FormSettingsTab />
        </div>
    );
}
