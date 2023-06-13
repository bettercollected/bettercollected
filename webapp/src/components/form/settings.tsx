import React from 'react';

import { useTranslation } from 'next-i18next';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import { localesGlobal } from '@app/constants/locales/global';

export default function FormSettings() {
    const { t } = useTranslation();
    return (
        <div className="md:max-w-[740px]">
            <p className="body1 !leading-none">{t(localesGlobal.settings)}</p>
            <p className="sm:max-w-[301px] body4 mt-4 mb-8 !text-black-700">Collaborators can import forms, delete forms, see responses and delete responses.</p>
            <FormSettingsTab />
        </div>
    );
}
