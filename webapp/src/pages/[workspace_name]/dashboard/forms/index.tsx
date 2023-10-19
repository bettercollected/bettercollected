import React from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardPinnedForms from '@app/components/workspace-dashboard/workspace-dashboard-pinned-forms';
import { localesCommon } from '@app/constants/locales/common';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function FormPage({ workspace, hasCustomDomain }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const { t } = useTranslation();

    const pinnedFormsQuery = {
        workspace_id: workspace.id,
        pinned_only: true
    };

    const pinnedFormsResponse = useGetWorkspaceFormsQuery(pinnedFormsQuery);
    const pinnedForms = pinnedFormsResponse?.data?.items || [];

    const { workspaceName } = useAppSelector(selectWorkspace);

    return (
        <SidebarLayout boxClassName="px-5 lg:px-10 pt-10">
            <NextSeo title={t(localesCommon.forms) + ' | ' + workspaceName} noindex={true} nofollow={true} />
            {pinnedForms?.length > 0 && <WorkspaceDashboardPinnedForms workspacePinnedForms={pinnedFormsResponse} title={t('PINNED_FORMS')} workspace={workspace} hasCustomDomain={hasCustomDomain} />}
            <WorkspaceDashboardForms showPagination={true} showButtons={pinnedForms?.length === 0} workspace={workspace} hasCustomDomain={hasCustomDomain} />
        </SidebarLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
