import React from 'react';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardOverview from '@app/components/workspace-dashboard/workspace-dashboard-overview';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceFormsQuery, useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';

export default function CreatorDashboard({ workspace, hasCustomDomain }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const workspaceQuery = {
        workspace_id: workspace.id
    };

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });
    const workspaceStats = useGetWorkspaceStatsQuery(workspace?.id, { pollingInterval: 30000 });

    return (
        <SidebarLayout>
            <WorkspaceDashboardOverview workspace={workspace} workspaceStats={workspaceStats?.data} />
            <div className="min-h-9 flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                <p className="sh1">Recent forms</p>
                <ImportFormsButton />
            </div>
            <WorkspaceDashboardForms hasCustomDomain={hasCustomDomain} workspace={workspace} workspaceForms={workspaceForms} />
        </SidebarLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
