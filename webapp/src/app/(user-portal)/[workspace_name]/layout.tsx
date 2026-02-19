'use client';

import React from 'react';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import ResponderPortalLayoutClient from '@Components/RespondersPortal/_components/ResponderPortalLayoutClient';
import { WorkspaceDispatcher } from '@app/app/_dispatcher/WorkspaceDispatcher';

export default function ResponderPortalLayout({
    children
}: {
    children: React.ReactNode
}) {
    const workspace = useAppSelector(selectWorkspace);

    return (
        <WorkspaceDispatcher workspace={workspace}>
            <ResponderPortalLayoutClient workspace={workspace} hasCustomDomain={false}>
                {children}
            </ResponderPortalLayoutClient>
        </WorkspaceDispatcher>
    );
}
