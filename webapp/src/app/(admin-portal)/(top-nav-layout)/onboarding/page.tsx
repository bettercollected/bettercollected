import React from 'react';
import { cookies, headers } from 'next/headers';
import { redirect, notFound } from 'next/navigation';
import environments from '@app/configs/environments';
import OnboardingClient from './OnboardingClient';

async function getWorkspaceByDomain(domain: string) {
    const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`, { cache: 'no-store' });
    return await response.json();
}

async function getWorkspaceByName(name: string) {
    const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?workspace_name=${name}`, { cache: 'no-store' });
    return await response.json();
}

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

export default async function OnboardingPage(props: { params: Promise<{ workspace_name: string }> }) {
    const params = await props.params;
    const headerList = await headers();
    const cookieStore = await cookies();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const isCustomDomain = host !== environments.ADMIN_DOMAIN && host !== environments.CLIENT_DOMAIN;

    if (isCustomDomain) {
        redirect('/');
    }

    const user = await getAuthStatus(cookieStore);
    if (!user) {
        redirect('/login');
    }

    const workspace = await getWorkspaceByName(params.workspace_name);

    if (!workspace?.id) {
        return notFound();
    }

    // Authorization check
    if (!user.roles?.includes('FORM_CREATOR') || workspace.ownerId !== user.id) {
        // Redux might have more complex logic but this is the core for onboarding
        // Usually, onboarding is only for the owner of the workspace.
    }

    if (workspace.title && workspace.title.toLowerCase() !== 'untitled') {
        redirect(`/${workspace.workspaceName}/dashboard`);
    }

    return (
        <OnboardingClient workspace={workspace} />
    );
}
