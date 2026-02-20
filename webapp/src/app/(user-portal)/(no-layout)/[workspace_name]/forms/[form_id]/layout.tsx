import { getWorkspaceByName } from '@app/app/(admin-portal)/(side-top-nav-layout)/[workspace_name]/dashboard/layout';
import { WorkspaceDispatcher } from '@app/app/_dispatcher/WorkspaceDispatcher';
import environments from '@app/configs/environments';
import { Alert, AlertDescription, AlertTitle } from '@app/shadcn/components/ui/alert';
import { AlertCircle } from 'lucide-react';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import React from 'react';

export default async function CustomDomainLayout({ children, params }: { children: React.ReactNode, params: Promise<{ workspace_name: string, form_id: string }> }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasClientDomain = host === environments.CLIENT_DOMAIN;
    const { workspace_name } = await params;

    if (!hasClientDomain) {
        notFound();
    }

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
