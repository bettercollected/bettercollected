import React, { useEffect } from 'react';

import ImportFormsMenu from '@app/components/dashboard/import-forms-menu';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardOverview from '@app/components/workspace-dashboard/workspace-dashboard-overview';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';

export default function CreatorDashboard({ workspace, hasCustomDomain }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const workspaceQuery = {
        workspace_id: workspace.id
    };

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });

    useEffect(() => {
        fetch('http://localhost:8000/api/v1/workspaces/6437b119ec2c5bde05404471/stats', {
            credentials: 'include'
        })
            .then((res) => {
                res.json().then((data) => {});
            })
            .catch((e) => {});
    }, []);

    return (
        <SidebarLayout>
            <WorkspaceDashboardOverview workspace={workspace} />
            <div className="h-9 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between mb-5">
                <p className="sh1">Recent forms</p>
                <ImportFormsMenu />
            </div>
            <WorkspaceDashboardForms hasCustomDomain={hasCustomDomain} workspace={workspace} workspaceForms={workspaceForms} />
        </SidebarLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
