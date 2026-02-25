import environments from '@app/configs/environments';
import { cookies, headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';
import React from 'react';
import WorkspaceDashboardLayout from "./_components/WorkspaceDashboardLayout";

export async function getWorkspaceByName(name: string) {
    const cookieStore = await cookies();
    const auth = (await cookieStore.get('Authorization'))?.value;
    const refresh = (await cookieStore.get('RefreshToken'))?.value;
    const cookieHeader = [
        auth ? `Authorization=${auth}` : '',
        refresh ? `RefreshToken=${refresh}` : ''
    ].filter(Boolean).join(';');

    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?workspace_name=${name}`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });
        if (!response.ok) return null;
        const data = await response.json();
        return Array.isArray(data) ? data[0] : data;
    } catch (error) {
        console.error('Error fetching workspace:', error);
        notFound();
    }
}

async function getAuthUser(cookieHeader: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching auth status:', error);
        return null;
    }
}

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
    const cookieStore = await cookies();
    const headerList = await headers();

    // Check for admin domain
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
    const isDomainAllowed = host === (environments.DASHBOARD_DOMAIN) || host === (environments.FORM_DOMAIN) || host.includes('localhost');

    if (!isDomainAllowed) {
        redirect('/');
    }

    const auth = (await cookieStore.get('Authorization'))?.value;
    const refresh = (await cookieStore.get('RefreshToken'))?.value;
    const cookieHeader = [
        auth ? `Authorization=${auth}` : '',
        refresh ? `RefreshToken=${refresh}` : ''
    ].filter(Boolean).join(';');

    const user = await getAuthUser(cookieHeader);

    if (!user) {
        redirect('/login');
    }

    return <WorkspaceDashboardLayout>{children}</WorkspaceDashboardLayout>;
}
