'use client';

import React from 'react';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import ResponderPortalContainer from '@Components/RespondersPortal/ResponderPortalContainer';

export default function WorkspaceIndexPage() {
    const workspace = useAppSelector(selectWorkspace);

    return (
        <ResponderPortalContainer
            workspace={workspace}
            hasCustomDomain={false}
        />
    );
}
