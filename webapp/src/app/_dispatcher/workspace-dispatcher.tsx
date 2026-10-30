'use client';

import { useEffect } from 'react';

import AuthStatusDispatcher from '@Components/hocs/auth-status-dispatcher';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace, setWorkspace } from '@app/store/workspaces/slice';
import { forgetResponseListOutside } from '@app/utils/response-list-memory';

export function WorkspaceDispatcher({ workspace, children }: { workspace: any; children: React.ReactNode }) {
    const dispatch = useAppDispatch();
    const storeWorkspace = useAppSelector(selectWorkspace);
    useEffect(() => {
        if (workspace?.id) {
            // the responses list remembered in another workspace (ids, a page, a search) is not carried into this one
            forgetResponseListOutside(workspace.id);
            dispatch(setWorkspace(workspace));
        }
    }, [workspace]);

    if (!storeWorkspace || storeWorkspace.id !== workspace?.id) {
        return <FullScreenLoader />;
    }

    return <AuthStatusDispatcher workspace={workspace}>{children}</AuthStatusDispatcher>;
}
