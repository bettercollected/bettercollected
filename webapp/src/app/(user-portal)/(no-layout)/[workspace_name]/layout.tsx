import { WorkspaceDispatcher } from '@app/app/_dispatcher/workspace-dispatcher';
import environments from '@app/configs/environments';
import { getWorkspaceByName } from '@app/lib/server/api';
import { Alert, AlertDescription, AlertTitle } from '@app/shadcn/components/ui/alert';
import { AlertCircle } from 'lucide-react';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import React from 'react';

export default async function ClientDomainLayout({ children, params }: { children: React.ReactNode, params: Promise<{ workspace_name: string }> }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasClientDomain = host === environments.FORM_DOMAIN;

    if (!hasClientDomain) {
        notFound();
    }

    const { workspace_name } = await params;

    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace?.id) {
        return (
            <div className="flex h-screen items-center justify-center p-4">
                <Alert variant="destructive" className="max-w-md">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>
                        Workspace not found or custom domain not configured properly.
                    </AlertDescription>
                </Alert>
            </div>
        );
    }

    return (
        <WorkspaceDispatcher workspace={workspace}>
            {children}
        </WorkspaceDispatcher>
    );
}
