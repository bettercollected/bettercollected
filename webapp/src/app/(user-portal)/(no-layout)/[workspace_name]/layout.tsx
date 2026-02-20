import { getWorkspaceByName } from '@app/app/(admin-portal)/(side-top-nav-layout)/[workspace_name]/dashboard/layout';
import { WorkspaceDispatcher } from '@app/app/_dispatcher/WorkspaceDispatcher';
import environments from '@app/configs/environments';
import { Alert, AlertDescription, AlertTitle } from '@app/shadcn/components/ui/alert';
import { AlertCircle } from 'lucide-react';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import React from 'react';

async function getWorkspaceByDomain(domain: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`, {
            next: { revalidate: 300 } // Cache for 5 minutes
        });
        if (!response.ok) return null;
        const data = await response.json();
        return Array.isArray(data) ? data[0] : data;
    } catch (error) {
        console.error('Error fetching workspace by domain:', error);
        return null;
    }
}

export default async function CustomDomainLayout({ children, params }: { children: React.ReactNode, params: Promise<{ workspace_name: string }> }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasClientDomain = host === environments.CLIENT_DOMAIN;

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
