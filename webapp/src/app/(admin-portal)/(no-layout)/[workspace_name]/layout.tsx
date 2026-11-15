import { notFound } from 'next/navigation';

import { WorkspaceDispatcher } from '@app/app/_dispatcher/workspace-dispatcher';
import AppThemeScope from '@app/components/app-theme/app-theme-scope';
import { getWorkspaceByName } from '@app/lib/server/api';
import { requireWorkspaceAccess } from '@app/lib/server/workspace-gate';

/**
 * Every workspace dashboard page. Only a member who may open the workspace
 * gets in: anyone else goes to the workspace selection screen with the same
 * "no access" notice, whether the workspace exists or not (the server
 * decides, from the user's own memberships only).
 */
export default async function WorkspaceDispatcherByNameLayout({ children, params }: { children: React.ReactNode; params: Promise<{ workspace_name: string }> }) {
    const { workspace_name } = await params;
    await requireWorkspaceAccess(workspace_name);

    const workspace = await getWorkspaceByName(workspace_name);
    if (!workspace?.id) {
        notFound();
    }

    // The workspace's app theme is part of the answer a member gets; the first HTML already carries it.
    return (
        <AppThemeScope workspaceId={workspace.id} initial={workspace.appTheme}>
            <WorkspaceDispatcher workspace={workspace}>{children}</WorkspaceDispatcher>
        </AppThemeScope>
    );
}
