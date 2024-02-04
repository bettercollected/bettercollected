import React from 'react';

import { useTranslation } from 'next-i18next';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import { localesCommon } from '@app/constants/locales/common';
import { formPage } from '@app/constants/locales/form-page';


export default function FormSettings() {
    const { t } = useTranslation();
    return (
        <div className="md:max-w-[740px]">
            <p className="sh1 !text-black-800 !leading-none">{t(localesCommon.settings)}</p>
            <p className="w-full body4 mt-4 mb-12 !text-black-700">{t(formPage.defaultDescription)}</p>
            <FormSettingsTab view="DEFAULT" />
        </div>
    );
}