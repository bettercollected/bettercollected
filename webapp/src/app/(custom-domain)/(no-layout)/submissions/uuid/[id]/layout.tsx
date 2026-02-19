import React from 'react';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import environments from '@app/configs/environments';
import SharedSubmissionLayoutClient from '@Components/RespondersPortal/_components/SharedSubmissionLayoutClient';

async function getWorkspaceByDomain(domain: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`, {
            next: { revalidate: 300 }
        });
        if (!response.ok) return null;
        const data = await response.json();
        return Array.isArray(data) ? data[0] : data;
    } catch (error) {
        console.error('Error fetching workspace:', error);
        return null;
    }
}

export default async function SubmissionUUIDLayout({
    children,
    params
}: {
    children: React.ReactNode;
    params: Promise<{ id: string }>
}) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
    const hasCustomDomain = host !== environments.ADMIN_DOMAIN && host !== environments.CLIENT_DOMAIN;

    const workspace = await getWorkspaceByDomain(host);

    // If custom domain, workspace must be found. If main domain, workspace is not tied to domain.
    if (hasCustomDomain && !workspace?.id) {
        notFound();
    }

    const { id } = await params;

    return (
        <SharedSubmissionLayoutClient
            workspaceId={workspace?.id}
            submissionId={id}
            hasCustomDomain={hasCustomDomain}
            isUUID={true}
        >
            {children}
        </SharedSubmissionLayoutClient>
    );
}
