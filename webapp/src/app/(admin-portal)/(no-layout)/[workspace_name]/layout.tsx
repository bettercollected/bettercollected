import { notFound, redirect } from 'next/navigation';

import { WorkspaceDispatcher } from '@app/app/_dispatcher/workspace-dispatcher';
import { getUser, getWorkspaceByName, getWorkspaceSelection } from '@app/lib/server/api';
import { selectWorkspaceUrl, workspaceDashboardPath } from '@app/lib/workspace-selection';

/**
 * Every workspace dashboard page. Only a member who may open the workspace
 * gets in: anyone else goes to the workspace selection screen with the same
 * "no access" notice, whether the workspace exists or not (the server
 * decides, from the user's own memberships only).
 */
export default async function WorkspaceDispatcherByNameLayout({ children, params }: { children: React.ReactNode; params: Promise<{ workspace_name: string }> }) {
    const { workspace_name } = await params;
    const dashboard = workspaceDashboardPath(workspace_name);

    const user = await getUser();
    if (!user) {
        redirect(`/login?${new URLSearchParams({ redirect_to: dashboard }).toString()}`);
    }

    const selection = await getWorkspaceSelection(dashboard);
    // no answer (the API is unreachable): the pages' own calls stay authorised by the API
    if (selection && !selection.next) {
        redirect(selectWorkspaceUrl(selection.notice));
    }

    const workspace = await getWorkspaceByName(workspace_name);
    if (!workspace?.id) {
        notFound();
    }

    return <WorkspaceDispatcher workspace={workspace}>{children}</WorkspaceDispatcher>;
}
