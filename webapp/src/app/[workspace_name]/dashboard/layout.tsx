import React from 'react';
import { cookies, headers } from 'next/headers';
import { redirect } from 'next/navigation';
import environments from '@app/configs/environments';
import ConditionalLayout from "./_components/conditional-layout";

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
            next: { revalidate: 0 }
        });
        if (!response.ok) return null;
        const data = await response.json();
        return Array.isArray(data) ? data[0] : data;
    } catch (error) {
        console.error('Error fetching workspace:', error);
        return null;
    }
}

async function getAuthUser(cookieHeader: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, {
            headers: {
                cookie: cookieHeader
            },
            next: { revalidate: 0 }
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching auth status:', error);
        return null;
    }
}

export default async function DashboardLayout({ children, params }: { children: React.ReactNode; params: { workspace_name: string } }) {
    const { workspace_name } = await params;
    const cookieStore = await cookies();
    const headerList = await headers();

    // Check for admin domain
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
    const isDomainAllowed = host === (process.env.ADMIN_DOMAIN || environments.ADMIN_DOMAIN) || host === (process.env.CLIENT_DOMAIN || environments.CLIENT_DOMAIN) || host.includes('localhost');

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

    return <ConditionalLayout>{children}</ConditionalLayout>;
}
