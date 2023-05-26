import React from 'react';

import { useTranslation } from 'next-i18next';

import ManageWorkspaceLayout from '@app/components/layout/manage-workspace';
import UpdateCustomDomain from '@app/components/settings/advanced/update-custom-domain';
import UpdateURL from '@app/components/settings/advanced/update-u-r-l';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import { advanceSetting } from '@app/constants/locales/advance-setting';

export default function AdvancedSettings({ workspace }: any) {
    return (
        <DashboardLayout>
            {/*<div className="h4">{t(advanceSetting.default)}</div>*/}
            <div className="max-w-[1000px]">
                <div className="h4">Manage URLs</div>
                <UpdateURL type="HANDLE" />
                <UpdateURL type="DOMAIN" />
            </div>
        </DashboardLayout>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
