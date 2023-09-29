import React from 'react';

import {useTranslation} from 'next-i18next';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import {localesCommon} from '@app/constants/locales/common';

export default function FormLinks() {
    const {t} = useTranslation();
    return (
        <div className="w-full md:max-w-[900px] mt-[5px]">
            <p className="sh1 !text-black-800 !leading-none">Form Link</p>
            <FormSettingsTab view='LINKS'/>
        </div>
    );
}


