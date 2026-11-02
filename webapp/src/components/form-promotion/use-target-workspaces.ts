import { useEffect, useState } from 'react';

import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGetAllMineWorkspacesQuery, workspacesApi } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export type TargetWorkspace = Pick<WorkspaceDto, 'id' | 'title' | 'workspaceName'>;

export interface TargetWorkspaces {
    /** The other workspaces of the signed-in person where they hold `form.create`. */
    workspaces: TargetWorkspace[];
    loading: boolean;
    failed: boolean;
}

/**
 * Where a form may be copied to: the person's other workspaces, each asked for the permissions they hold there (the same
 * answer the dashboard uses, `GET /workspaces/{id}/permissions`), keeping those with `form.create`. Asked only while
 * `enabled` (the dialog is open), so nothing is requested while copying is off or the dialog is closed. The server decides
 * again on every copy: this only keeps the list honest.
 */
export function useTargetWorkspaces(enabled: boolean): TargetWorkspaces {
    const dispatch = useAppDispatch();
    const current = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const userId: string = auth?.id ?? '';
    const mine = useGetAllMineWorkspacesQuery(undefined, { skip: !enabled });
    const [state, setState] = useState<{ workspaces: TargetWorkspace[]; loading: boolean; failed: boolean }>({ workspaces: [], loading: true, failed: false });

    const others: TargetWorkspace[] = (Array.isArray(mine.data) ? (mine.data as WorkspaceDto[]) : []).filter((w) => w?.id && w.id !== current?.id && !w.disabled).map((w) => ({ id: w.id, title: w.title, workspaceName: w.workspaceName }));
    const key = others.map((w) => w.id).join(',');

    useEffect(() => {
        if (!enabled || mine.isLoading) return;
        if (mine.isError) {
            setState({ workspaces: [], loading: false, failed: true });
            return;
        }
        if (!userId) return;
        let cancelled = false;
        const subscriptions: Array<{ unsubscribe: () => void }> = [];
        setState((previous) => ({ ...previous, loading: true, failed: false }));
        Promise.all(
            others.map(async (workspace) => {
                const request: any = dispatch(workspacesApi.endpoints.getWorkspacePermissions.initiate({ workspaceId: workspace.id, userId }));
                subscriptions.push(request);
                const result = await request;
                const permissions: string[] = result?.data?.permissions ?? [];
                return permissions.includes(WorkspacePermission.FORM_CREATE) ? workspace : null;
            })
        )
            .then((found) => {
                if (!cancelled) setState({ workspaces: found.filter((w): w is TargetWorkspace => w !== null), loading: false, failed: false });
            })
            .catch(() => {
                if (!cancelled) setState({ workspaces: [], loading: false, failed: true });
            });
        return () => {
            cancelled = true;
            subscriptions.forEach((s) => s.unsubscribe());
        };
        // `key` stands for the list of ids
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [enabled, mine.isLoading, mine.isError, key, userId, dispatch]);

    return { workspaces: state.workspaces, loading: enabled && (mine.isLoading || state.loading), failed: state.failed };
}
