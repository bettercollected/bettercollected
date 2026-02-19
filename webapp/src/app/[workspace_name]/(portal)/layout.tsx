'use client';

import React from 'react';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import ResponderPortalLayoutClient from './_components/ResponderPortalLayoutClient';

export default function ResponderPortalLayout({
    children
}: {
    children: React.ReactNode
}) {
    const workspace = useAppSelector(selectWorkspace);

    return (
        <ResponderPortalLayoutClient workspace={workspace} hasCustomDomain={false}>
            {children}
        </ResponderPortalLayoutClient>
    );
}
