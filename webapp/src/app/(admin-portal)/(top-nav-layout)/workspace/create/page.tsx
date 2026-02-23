import React from 'react';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import environments from '@app/configs/environments';
import Onboarding from '@app/containers/Onboarding';

async function getUserStatus() {
    const cookieStore = await cookies();
    const auth = cookieStore.get('Authorization')?.value;
    const refresh = cookieStore.get('RefreshToken')?.value;

    const cookieHeader = [
        auth ? `Authorization=${auth}` : '',
        refresh ? `RefreshToken=${refresh}` : ''
    ].filter(Boolean).join(';');

    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store' // Don't cache auth status
        });

        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching user status:', error);
        return null;
    }
}

export default async function CreateWorkspacePage() {
    const user = await getUserStatus();

    if (!user?.roles?.includes('FORM_CREATOR') || user?.plan !== 'PRO') {
        redirect('/');
    }

    return <Onboarding createWorkspace />;
}
