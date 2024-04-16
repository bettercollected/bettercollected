'use client';

import AuthStatusDispatcher from '@Components/HOCs/AuthStatusDispatcher';
import ServerSideWorkspaceDispatcher from '@Components/HOCs/ServerSideWorkspaceDispatcher';
import useWorkspace from '@app/store/jotai/workspace';

export default function ReduxWrapperAppRouter({ children }: any) {
    const { workspace } = useWorkspace();
    return (
        <ServerSideWorkspaceDispatcher workspace={workspace}>
            <AuthStatusDispatcher workspace={workspace}>{children}</AuthStatusDispatcher>
        </ServerSideWorkspaceDispatcher>
    );
}
