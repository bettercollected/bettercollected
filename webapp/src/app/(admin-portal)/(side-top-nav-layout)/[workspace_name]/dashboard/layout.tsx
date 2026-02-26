import environments from '@app/configs/environments';
import { getWorkspaceByName as getWorkspace, getUser } from '@app/lib/server/api';
import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import React from 'react';
import WorkspaceDashboardLayout from "./_components/workspace-dashboard-layout";

export async function getWorkspaceByName(name: string) {
    return await getWorkspace(name);
}

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
    const headerList = await headers();

    // Check for admin domain
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
    const isDomainAllowed = host === (environments.DASHBOARD_DOMAIN) || host === (environments.FORM_DOMAIN) || host.includes('localhost');

    if (!isDomainAllowed) {
        redirect('/');
    }

    const user = await getUser();

    if (!user) {
        redirect('/login');
    }

    return <WorkspaceDashboardLayout>{children}</WorkspaceDashboardLayout>;
}
