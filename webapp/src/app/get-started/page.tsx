import React from 'react';
import { cookies, headers } from 'next/headers';
import { redirect } from 'next/navigation';
import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import GetStartedClient from './GetStartedClient';

async function getAuthStatus(cookieStore: any) {
    const auth = cookieStore.get('Authorization')?.value;
    const refresh = cookieStore.get('RefreshToken')?.value;

    if (!auth) return null;

    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, {
            headers: {
                cookie: `Authorization=${auth}; RefreshToken=${refresh}`
            }
        });
        return await response.json();
    } catch (error) {
        return null;
    }
}

async function getMyWorkspaces(cookieStore: any) {
    const auth = cookieStore.get('Authorization')?.value;
    const refresh = cookieStore.get('RefreshToken')?.value;

    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/mine`, {
            headers: {
                cookie: `Authorization=${auth}; RefreshToken=${refresh}`
            }
        });
        return await response.json();
    } catch (error) {
        return [];
    }
}

export default async function GetStartedPage() {
    const headerList = headers();
    const cookieStore = cookies();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const isCustomDomain = host !== environments.ADMIN_DOMAIN && host !== environments.CLIENT_DOMAIN;

    // Translation locale (defaulting to en for now as per other App Router components)
    // In a full implementation, this might come from middleware/params
    const locale = '';

    if (isCustomDomain) {
        redirect(`/${locale}`);
    }

    const user = await getAuthStatus(cookieStore);

    if (user?.roles?.includes('FORM_CREATOR')) {
        const userWorkspaces = await getMyWorkspaces(cookieStore);
        if (userWorkspaces && userWorkspaces.length > 0) {
            const defaultWorkspace = userWorkspaces.find((ws: WorkspaceDto) => ws.ownerId === user.id) || userWorkspaces[0];

            if (!defaultWorkspace?.title || defaultWorkspace.title.toLowerCase() === 'untitled') {
                redirect(`/${locale}${defaultWorkspace.workspaceName}/onboarding`);
            } else {
                redirect(`/${locale}${defaultWorkspace.workspaceName}/dashboard`);
            }
        }
    }

    return <GetStartedClient locale={locale} />;
}
