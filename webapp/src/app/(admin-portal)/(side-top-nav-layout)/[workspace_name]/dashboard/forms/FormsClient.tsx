'use client';

import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardPinnedForms from '@app/components/workspace-dashboard/workspace-dashboard-pinned-forms';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useTranslation } from 'react-i18next';

export default function FormsClient({ workspace, hasCustomDomain }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const { t } = useTranslation();

    const pinnedFormsQuery = {
        workspace_id: workspace.id,
        pinned_only: true
    };

    const pinnedFormsResponse = useGetWorkspaceFormsQuery(pinnedFormsQuery, { skip: !workspace.id });
    const pinnedForms = pinnedFormsResponse?.data?.items || [];

    const { workspaceName } = useAppSelector(selectWorkspace);

    return (
        <>
            {pinnedForms?.length > 0 && (
                <WorkspaceDashboardPinnedForms
                    workspacePinnedForms={pinnedFormsResponse}
                    title={t('PINNED_FORMS')}
                    workspace={workspace}
                    hasCustomDomain={hasCustomDomain}
                />
            )}
            <WorkspaceDashboardForms
                showPagination={true}
                showButtons={pinnedForms?.length === 0}
                workspace={workspace}
                hasCustomDomain={hasCustomDomain}
            />
        </>
    );
}
