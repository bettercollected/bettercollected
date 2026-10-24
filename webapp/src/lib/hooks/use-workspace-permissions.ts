import { useCallback, useEffect, useMemo, useRef } from 'react';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { WORKSPACE_PERMISSIONS_TAG, useGetWorkspacePermissionsQuery, workspacesApi } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/**
 * What the signed-in user may do in the current workspace, from
 * `GET /workspaces/{id}/permissions`. `can(permission)` is false until the
 * permissions have loaded (and when the request fails), so admin controls
 * never flash for members. The cache is per user and is dropped when the
 * signed-in user changes or signs out. `ready` turns true once the answer has
 * arrived, for choices that must not be made on the empty set.
 */
export function useWorkspacePermissions() {
    const dispatch = useAppDispatch();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const workspaceId: string | undefined = workspace?.id;
    const userId: string = auth?.id ?? '';

    const previousUser = useRef(userId);
    useEffect(() => {
        if (previousUser.current !== userId) {
            previousUser.current = userId;
            dispatch(workspacesApi.util.invalidateTags([WORKSPACE_PERMISSIONS_TAG]));
        }
    }, [dispatch, userId]);

    const { data, isLoading, isError, isSuccess } = useGetWorkspacePermissionsQuery({ workspaceId: workspaceId as string, userId }, {
        skip: !workspaceId || !userId,
        // one fetch per workspace: every list row asks
        refetchOnMountOrArgChange: false
    });
    const permissions = useMemo(() => new Set<WorkspacePermission>(!userId || isError ? [] : (data?.permissions ?? [])), [data, isError, userId]);
    const can = useCallback((permission: WorkspacePermission) => permissions.has(permission), [permissions]);
    // Settled: the answer for this workspace and user has arrived (or failed,
    // which grants nothing). False while the workspace or user is unknown.
    const ready = !!workspaceId && !!userId && (isSuccess || isError);
    return { can, permissions, isLoading, ready };
}
