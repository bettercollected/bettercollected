import React from 'react';

import { useTranslation } from 'next-i18next';

import Button from '@Components/Common/Input/Button';

import ImportFormsButton from '@app/components/form-integrations/import-forms-button';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardOverview from '@app/components/workspace-dashboard/workspace-dashboard-overview';
import { formsConstant } from '@app/constants/locales/forms';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceFormsQuery, useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';

export default function CreatorDashboard({ workspace, hasCustomDomain, ...props }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const { t } = useTranslation();

    const workspaceQuery = {
        workspace_id: workspace.id
    };

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });
    const workspaceStats = useGetWorkspaceStatsQuery(workspace?.id, { pollingInterval: 30000 });

    return (
        <DashboardLayout>
            <WorkspaceDashboardOverview workspace={workspace} workspaceStats={workspaceStats?.data} />
            <div className="min-h-9 flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                <p className="sh1">{t(formsConstant.recentForms)}</p>
                <ImportFormsButton />
            </div>
            <WorkspaceDashboardForms hasCustomDomain={hasCustomDomain} workspace={workspace} workspaceForms={workspaceForms} />
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
