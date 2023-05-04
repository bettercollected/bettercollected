import React, { useEffect } from 'react';

import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppDispatch } from '@app/store/hooks';
import { setWorkspace } from '@app/store/workspaces/slice';

interface IServerSideWorkspaceDispatcherProps {
    children: React.ReactNode | React.ReactNode[];
    workspace: WorkspaceDto | null | undefined;
}

export default function ServerSideWorkspaceDispatcher({ children, workspace }: IServerSideWorkspaceDispatcherProps) {
    const dispatch = useAppDispatch();

    useEffect(() => {
        if (workspace) dispatch(setWorkspace(workspace));
    }, [workspace]);

    return <>{children}</>;
}
