import React from 'react';
import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import environments from '@app/configs/environments';
import TemplatePageClient from './TemplatePageClient';

export default async function TemplatePage({ params }: { params: { id: string } }) {
    const headerList = await headers();
    const host = headerList.get('host') || '';
    const forwardedHost = headerList.get('x-forwarded-host');

    const requestHost = forwardedHost || host;
    const hasAdminDomain = requestHost === environments.ADMIN_DOMAIN;

    if (!hasAdminDomain) {
        redirect('/');
    }

    const { id } = await params;

    return <TemplatePageClient templateId={id} />;
}
