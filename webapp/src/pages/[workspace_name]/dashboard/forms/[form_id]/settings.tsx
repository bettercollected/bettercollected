import React from 'react';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import FormPageLayout from '@app/components/sidebar/form-page-layout';

export default function Settings(props: any) {
    return (
        <FormPageLayout {...props}>
            <FormSettingsTab />
        </FormPageLayout>
    );
}

export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
