import environments from '@app/configs/environments';
import { Alert, AlertDescription, AlertTitle } from '@app/shadcn/components/ui/alert';
import ResponderPortalLayoutClient from '@Components/RespondersPortal/_components/ResponderPortalLayoutClient';
import { AlertCircle } from 'lucide-react';
import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import React from 'react';
import { WorkspaceDispatcher } from '../../_dispatcher/WorkspaceDispatcher';

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

export default async function CustomDomainLayout({ children }: { children: React.ReactNode }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasCustomDomain = host !== environments.ADMIN_DOMAIN && host !== environments.CLIENT_DOMAIN && !host.includes(environments.ADMIN_DOMAIN);

    // If not custom domain (e.g. localhost), we usually don't support these routes unless we map localhost to a custom domain.
    // For development, we assume localhost is admin domain usually.

    if (!hasCustomDomain) {
        // Redirect to login if accessed directly on admin domain
        redirect('/login');
    }

    const workspace = await getWorkspaceByDomain(host);

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
            <ResponderPortalLayoutClient hasCustomDomain={true}>
                {children}
            </ResponderPortalLayoutClient>
        </WorkspaceDispatcher>
    );
}
