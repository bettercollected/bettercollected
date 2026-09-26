import React from 'react';

import { Metadata } from 'next';
import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

import ResponderPortalLayoutClient from '@Components/responder-portal/responder-portal-layout-client';
import { AlertCircle } from 'lucide-react';

import environments from '@app/configs/environments';
import { resolveCustomDomainWorkspace } from '@app/lib/server/custom-domain';
import { Alert, AlertDescription, AlertTitle } from '@app/shadcn/components/ui/alert';

import { WorkspaceDispatcher } from '../../_dispatcher/workspace-dispatcher';

export async function generateMetadata(): Promise<Metadata> {
    const { workspace } = await resolveCustomDomainWorkspace();

    return {
        title: workspace?.name || 'Workspace',
        description: `Welcome to ${workspace?.name || 'your workspace'}`
    };
}

export default async function CustomDomainLayout({ children }: { children: React.ReactNode }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasCustomDomain = host !== environments.DASHBOARD_DOMAIN && host !== environments.FORM_DOMAIN && !host.includes(environments.DASHBOARD_DOMAIN);

    if (!hasCustomDomain) {
        redirect('/login');
    }

    const { workspace } = await resolveCustomDomainWorkspace();

    if (!workspace?.id) {
        return (
            <div className="flex h-screen items-center justify-center p-4">
                <Alert variant="destructive" className="max-w-md">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>Workspace not found or custom domain not configured properly.</AlertDescription>
                </Alert>
            </div>
        );
    }

    return (
        <WorkspaceDispatcher workspace={workspace}>
            <ResponderPortalLayoutClient hasCustomDomain={true}>{children}</ResponderPortalLayoutClient>
        </WorkspaceDispatcher>
    );
}
