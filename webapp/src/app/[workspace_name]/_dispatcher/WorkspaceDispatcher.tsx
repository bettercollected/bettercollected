'use client';

import { useEffect } from 'react';

import { useAppDispatch } from '@app/store/hooks';
import { setWorkspace } from '@app/store/workspaces/slice';

export function WorkspaceDispatcher({ workspace, children }: { workspace: any; children: React.ReactNode }) {
    const dispatch = useAppDispatch();
    useEffect(() => {
        if (workspace?.id) {
            dispatch(setWorkspace(workspace));
        }
    }, [workspace]);

    return <>{children}</>;
}
