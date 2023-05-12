import React from 'react';

import { useTranslation } from 'next-i18next';

import ManageWorkspaceLayout from '@app/components/layout/manage-workspace';
import WorkspaceImage from '@app/components/settings/basic-information/worksapce-image';
import WorkspaceBanner from '@app/components/settings/basic-information/workspace-banner';
import WorkspaceInfo from '@app/components/settings/basic-information/workspace-info';
import { workspaceConstant } from '@app/constants/locales';

export default function ManageWorkspace({ workspace }: any) {
    const { t } = useTranslation();
    return (
        <ManageWorkspaceLayout>
            <div className="h4">{t(workspaceConstant.manage)}</div>
            <WorkspaceBanner />
            <WorkspaceImage />
            <WorkspaceInfo workspace={workspace} />
        </ManageWorkspaceLayout>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
