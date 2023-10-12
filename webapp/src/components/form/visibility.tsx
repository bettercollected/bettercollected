import React from 'react';

import { useTranslation } from 'next-i18next';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import { formPage } from '@app/constants/locales/form-page';

export default function FormVisibilities() {
    const { t } = useTranslation();
    return (
        <div className="w-full md:max-w-[900px]">
            <p className="sh1 !text-black-800 !leading-none">{t(formPage.visibilityTitle)}</p>
            <p className="w-full body4 mt-4 mb-12 !text-black-700">{t(formPage.visibilityDescription)}</p>
            <FormSettingsTab view="VISIBILITY" />
        </div>
    );
}
