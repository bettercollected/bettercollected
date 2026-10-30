import { redirect } from 'next/navigation';

import { getWorkspaceTarget } from '@app/lib/server/api';
import { SELECT_WORKSPACE_PATH, selectWorkspaceUrl, workspaceDashboardPath } from '@app/lib/workspace-selection';

/**
 * The check every page of a workspace's dashboard (and its onboarding) runs
 * before it reads anything about the workspace: only a member who may open
 * it gets past. The server decides from the user's own memberships, so a
 * workspace they aren't in and one that doesn't exist get the same answer.
 *
 * - nobody signed in: the sign-in page, then back to this workspace;
 * - not allowed: the selection screen with its fixed notice (or without one
 *   when the workspace needs its single sign-on first, whose row starts it);
 * - no answer (the API down, a timeout, an over-long handle): the selection
 *   screen too, never a page whose outcome depends on the workspace.
 */
export async function requireWorkspaceAccess(workspaceName: string): Promise<void> {
    const dashboard = workspaceDashboardPath(workspaceName);
    const { status, data } = await getWorkspaceTarget(dashboard);
    if (status === 401) {
        redirect(`/login?${new URLSearchParams({ redirect_to: dashboard }).toString()}`);
    }
    if (!data) {
        redirect(SELECT_WORKSPACE_PATH);
    }
    if (!data.next) {
        redirect(selectWorkspaceUrl(data.notice));
    }
}
