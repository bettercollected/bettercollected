import React from 'react';

import { useTranslation } from 'next-i18next';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import { localesDefault } from '@app/constants/locales';

export default function Settings(props: any) {
    const { t } = useTranslation();
    return (
        <FormPageLayout {...props}>
            <div className="heading4">{t(localesDefault.settings)}</div>
            <FormSettingsTab />
        </FormPageLayout>
    );
}

export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
