'use client';

import AuthStatusDispatcher from '@Components/HOCs/AuthStatusDispatcher';
import ServerSideWorkspaceDispatcher from '@Components/HOCs/ServerSideWorkspaceDispatcher';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ReduxWrapperAppRouter({ children }: any) {
    const workspace = useAppSelector(selectWorkspace);
    return (
        <ServerSideWorkspaceDispatcher workspace={workspace}>
            <AuthStatusDispatcher workspace={workspace}>{children}</AuthStatusDispatcher>
        </ServerSideWorkspaceDispatcher>
    );
}
