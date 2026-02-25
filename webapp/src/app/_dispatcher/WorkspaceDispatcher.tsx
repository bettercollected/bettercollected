'use client';

import { useEffect } from 'react';

import AuthStatusDispatcher from '@app/components/HOCs/AuthStatusDispatcher';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace, setWorkspace } from '@app/store/workspaces/slice';

export function WorkspaceDispatcher({ workspace, children }: { workspace: any; children: React.ReactNode }) {
    const dispatch = useAppDispatch();
    const storeWorkspace = useAppSelector(selectWorkspace);
    useEffect(() => {
        if (workspace?.id) {
            dispatch(setWorkspace(workspace));
        }
    }, [workspace]);

    if (!storeWorkspace || storeWorkspace.id !== workspace?.id) {
        return <FullScreenLoader />;
    }

    return <AuthStatusDispatcher workspace={workspace}>{children}</AuthStatusDispatcher>;
}
