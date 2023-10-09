import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import StyledPagination from '@Components/Common/Pagination';

import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import globalConstants from '@app/constants/global';
import { localesCommon } from '@app/constants/locales/common';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function FormPage({ workspace, hasCustomDomain }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const { t } = useTranslation();

    const [workspaceQuery, setWorkspaceQuery] = useState({
        workspace_id: workspace.id,
        page: 1,
        size: globalConstants.pageSize
    });

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });

    const pinnedFormsQuery = {
        workspace_id: workspace.id,
        pinned_only: true
    };

    const pinnedFormsResponse = useGetWorkspaceFormsQuery(pinnedFormsQuery);
    const pinnedForms = pinnedFormsResponse?.data?.items || [];

    const forms = workspaceForms?.data?.items || [];

    const handlePageChange = (event: any, page: number) => {
        setWorkspaceQuery({
            ...workspaceQuery,
            page: page
        });
    };

    const { workspaceName } = useAppSelector(selectWorkspace);

    return (
        <SidebarLayout boxClassName="px-5 lg:px-10 pt-10">
            <NextSeo title={t(localesCommon.forms) + ' | ' + workspaceName} noindex={true} nofollow={true} />
            {pinnedForms?.length > 0 && <WorkspaceDashboardForms showPinned={false} workspaceForms={pinnedFormsResponse} title="Pinned Forms" workspace={workspace} hasCustomDomain={hasCustomDomain} />}
            <WorkspaceDashboardForms workspaceForms={workspaceForms} showButtons={pinnedForms?.length === 0} workspace={workspace} hasCustomDomain={hasCustomDomain} />
            {Array.isArray(forms) && workspaceForms?.data?.total > globalConstants.pageSize && (
                <div className="mt-8 flex justify-center">
                    <StyledPagination shape="rounded" count={workspaceForms?.data?.pages || 0} page={workspaceQuery.page || 1} onChange={handlePageChange} />
                </div>
            )}
        </SidebarLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
