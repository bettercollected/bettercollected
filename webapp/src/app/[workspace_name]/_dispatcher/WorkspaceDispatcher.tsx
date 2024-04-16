'use client';

import { useEffect } from 'react';

import useWorkspace from '@app/store/jotai/workspace';
import { useAppDispatch } from '@app/store/hooks';
import { setWorkspace } from '@app/store/workspaces/slice';

export function WorkspaceDispatcher({ workspace, children }: { workspace: any; children: React.ReactNode }) {
    const { setWorkspace: setWorkspaceJotai } = useWorkspace();

    const dispatch = useAppDispatch();
    useEffect(() => {
        if (workspace?.id) {
            setWorkspaceJotai(workspace);
            dispatch(setWorkspace(workspace));
        }
    }, [workspace]);

    return <>{children}</>;
}
