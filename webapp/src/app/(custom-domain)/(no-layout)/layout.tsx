import React from 'react';

import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import { AlertCircle } from 'lucide-react';

import environments from '@app/configs/environments';
import { resolveCustomDomainWorkspace } from '@app/lib/server/custom-domain';
import { Alert, AlertDescription, AlertTitle } from '@app/shadcn/components/ui/alert';

import { WorkspaceDispatcher } from '../../_dispatcher/workspace-dispatcher';

export default async function CustomDomainLayout({ children }: { children: React.ReactNode }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasCustomDomain = host !== environments.DASHBOARD_DOMAIN && host !== environments.FORM_DOMAIN;

    if (!hasCustomDomain) {
        if (host === environments.DASHBOARD_DOMAIN) {
            redirect('/login');
        } else {
            notFound();
        }
    }

    const { workspace } = hasCustomDomain ? await resolveCustomDomainWorkspace() : { workspace: null };

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

    return <WorkspaceDispatcher workspace={workspace}>{children}</WorkspaceDispatcher>;
}
