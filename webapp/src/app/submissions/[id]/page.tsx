import React from 'react';
import { headers } from 'next/headers';
import { redirect, notFound } from 'next/navigation';
import environments from '@app/configs/environments';
import SubmissionWrapper from './SubmissionWrapper';

async function getWorkspaceByDomain(domain: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`, {
            next: { revalidate: 300 }
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching workspace:', error);
        return null;
    }
}

export default async function SubmissionPage({ params }: { params: Promise<{ id: string }> }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
    const hasCustomDomain = host !== environments.ADMIN_DOMAIN && host !== environments.CLIENT_DOMAIN;

    if (!hasCustomDomain) {
        redirect('/');
    }

    const workspace = await getWorkspaceByDomain(host);
    if (!workspace?.id) {
        notFound();
    }

    const { id } = await params;

    return <SubmissionWrapper workspace={workspace} submissionId={id} hasCustomDomain={true} />;
}
