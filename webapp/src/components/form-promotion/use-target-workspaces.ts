import { useEffect, useState } from 'react';

import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGetAllMineWorkspacesQuery, workspacesApi } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/** How many workspaces' permissions are asked for at once. */
export const PERMISSION_CHECKS_AT_ONCE = 4;

/**
 * Run `task` over `items` with at most `limit` running at once, in order of start; `each` is called after every one finishes.
 * `stopped` is asked before each item starts: once it says true nothing more is started (the dialog was closed).
 */
export async function runLimited<T>(items: T[], limit: number, task: (item: T) => Promise<void>, each?: () => void, stopped?: () => boolean): Promise<void> {
    let next = 0;
    const worker = async () => {
        while (next < items.length && !stopped?.()) {
            const item = items[next++];
            await task(item);
            each?.();
        }
    };
    await Promise.all(Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, worker));
}

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
        const subscriptions = new Set<{ unsubscribe: () => void }>();
        const allowed = new Map<string, boolean>();
        let failures = 0;
        setState({ workspaces: [], loading: true, failed: false });
        // at most a few permission requests at a time, however many workspaces there are; each answer shows its workspace at once
        runLimited(
            others,
            PERMISSION_CHECKS_AT_ONCE,
            async (workspace) => {
                const request: any = dispatch(workspacesApi.endpoints.getWorkspacePermissions.initiate({ workspaceId: workspace.id, userId }));
                subscriptions.add(request);
                try {
                    const result = await request;
                    // an answer that is an error (the request failed) is no answer, not "no permission"
                    if (result?.error || !result?.data) failures += 1;
                    const permissions: string[] = result?.data?.permissions ?? [];
                    allowed.set(workspace.id, permissions.includes(WorkspacePermission.FORM_CREATE));
                } catch {
                    // one workspace that does not answer is one that is not offered
                    failures += 1;
                    allowed.set(workspace.id, false);
                } finally {
                    subscriptions.delete(request);
                    request?.unsubscribe?.();
                }
            },
            () => {
                if (!cancelled) setState((previous) => ({ ...previous, workspaces: others.filter((w) => allowed.get(w.id)) }));
            },
            () => cancelled
        ).then(() => {
            // when every request failed the person sees an error, not "no other workspace where you can create forms"
            if (!cancelled) setState({ workspaces: others.filter((w) => allowed.get(w.id)), loading: false, failed: others.length > 0 && failures === others.length });
        });
        return () => {
            cancelled = true;
            subscriptions.forEach((s) => s.unsubscribe?.());
        };
        // `key` stands for the list of ids
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [enabled, mine.isLoading, mine.isError, key, userId, dispatch]);

    return { workspaces: state.workspaces, loading: enabled && (mine.isLoading || state.loading), failed: state.failed };
}
