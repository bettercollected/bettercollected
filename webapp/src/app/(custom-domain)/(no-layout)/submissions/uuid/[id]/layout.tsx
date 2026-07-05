import environments from '@app/configs/environments';
import { getWorkspaceByDomain } from '@app/lib/server/api';
import SharedSubmissionLayoutClient from '@Components/responder-portal/shared-submission-layout-client';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import React from 'react';

export default async function SubmissionUUIDLayout({
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

    if (hasCustomDomain && !workspace?.id) {
        notFound();
    }

    const { id } = await params;

    return (
        <SharedSubmissionLayoutClient
            submissionId={id}
            hasCustomDomain={hasCustomDomain}
            isUUID={true}
        >
            {children}
        </SharedSubmissionLayoutClient>
    );
}
