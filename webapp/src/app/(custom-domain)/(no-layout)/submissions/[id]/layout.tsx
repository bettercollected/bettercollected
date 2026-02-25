import SharedSubmissionLayoutClient from '@Components/responder-portal/shared-submission-layout-client';
import environments from '@app/configs/environments';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import React from 'react';

async function getWorkspaceByDomain(domain: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`, {
            cache: 'no-store'
        });
        if (!response.ok) return null;
        const data = await response.json();
        return Array.isArray(data) ? data[0] : data;
    } catch (error) {
        console.error('Error fetching workspace:', error);
        return null;
    }
}

export default async function SubmissionLayout({
    children,
    params
}: {
    children: React.ReactNode;
    params: Promise<{ id: string }>
}) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
    const hasCustomDomain = host !== environments.DASHBOARD_DOMAIN && host !== environments.FORM_DOMAIN;

    const workspace = await getWorkspaceByDomain(host);

    // If custom domain, workspace must be found. If main domain, workspace is not tied to domain.
    if (hasCustomDomain && !workspace?.id) {
        notFound();
    }

    const { id } = await params;

    return (
        <SharedSubmissionLayoutClient
            submissionId={id}
            hasCustomDomain={hasCustomDomain}
            isUUID={false}
        >
            {children}
        </SharedSubmissionLayoutClient>
    );
}
