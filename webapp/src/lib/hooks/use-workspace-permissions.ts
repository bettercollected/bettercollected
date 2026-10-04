import { useCallback, useMemo } from 'react';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspacePermissionsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/**
 * What the signed-in user may do in the current workspace, from
 * `GET /workspaces/{id}/permissions`. `can(permission)` is false until the
 * permissions have loaded, so admin controls never flash for members.
 */
export function useWorkspacePermissions() {
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const workspaceId: string | undefined = workspace?.id;
    const { data, isLoading } = useGetWorkspacePermissionsQuery(workspaceId as string, {
        skip: !workspaceId || !auth?.id,
        // one fetch per workspace: every list row asks
        refetchOnMountOrArgChange: false
    });
    const permissions = useMemo(() => new Set<WorkspacePermission>(data?.permissions ?? []), [data]);
    const can = useCallback((permission: WorkspacePermission) => permissions.has(permission), [permissions]);
    return { can, permissions, isLoading };
}
