'use client';

import { useEffect } from 'react';

import useWorkspace from '@app/store/jotai/workspace';

export function WorkspaceDispatcher({
    workspace,
    children
}: {
    workspace: any;
    children: React.ReactNode;
}) {
    const { setWorkspace } = useWorkspace();
    useEffect(() => {
        setWorkspace(workspace);
    }, [workspace]);

    return <>{children}</>;
}
