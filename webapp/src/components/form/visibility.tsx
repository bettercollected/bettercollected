import React from 'react';

import { useTranslation } from 'next-i18next';

import FormSettingsTab from '@app/components/dashboard/form-settings';


export default function FormVisibilities() {
    const { t } = useTranslation();
    return (
        <div className="w-full md:max-w-[900px]">
            <p className="sh1 !text-black-800 !leading-none">Form Visibility</p>
            <p className="w-full body4 mt-4 mb-12 !text-black-700">Your choice of form visibility directly impacts who can view and access the form within your form page.</p>
            <FormSettingsTab view="VISIBILITY" />
        </div>
    );
}