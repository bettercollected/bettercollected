import React from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import UpdateURL from '@app/components/settings/advanced/update-u-r-l';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import { metaDataTitle } from '@app/constants/locales/meta-data-title';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';


export default function AdvancedSettings({ workspace }: any) {
    const { workspaceName } = useAppSelector(selectWorkspace);
    const { t } = useTranslation();
    return (
        <DashboardLayout boxClassName="px-5 py-10 lg:px-10">
            <NextSeo title={t(metaDataTitle.manageUrls) + ' | ' + workspaceName} noindex={true} nofollow={true} />
            {/*<div className="h4">{t(advanceSetting.default)}</div>*/}
            <div className="max-w-[1000px]">
                <div className="h4">{t(metaDataTitle.manageUrls)}</div>
                <UpdateURL type="HANDLE" />
                <UpdateURL type="DOMAIN" />
            </div>
        </DashboardLayout>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';