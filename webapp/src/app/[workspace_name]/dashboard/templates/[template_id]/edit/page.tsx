import React from 'react';
import { cookies } from 'next/headers';
import { notFound, redirect } from 'next/navigation';
import environments from '@app/configs/environments';
import EditTemplateClient from './EditTemplateClient';

async function getWorkspaceByName(name: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?workspace_name=${name}`, {
            next: { revalidate: 300 }
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching workspace by name:', error);
        return null;
    }
}

async function getTemplate(templateId: string, workspaceId: string, cookieHeader: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/templates/${templateId}?workspace_id=${workspaceId}`, {
            headers: {
                cookie: cookieHeader
            },
            next: { revalidate: 0 }
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching template:', error);
        return null;
    }
}

export default async function EditTemplatePage({ params }: { params: { workspace_name: string, template_id: string } }) {
    const { workspace_name, template_id } = await params;

    const workspace = await getWorkspaceByName(workspace_name);
    if (!workspace?.id) {
        notFound();
    }

    const cookieStore = await cookies();
    const auth = cookieStore.get('Authorization')?.value;
    const refresh = cookieStore.get('RefreshToken')?.value;
    const cookieHeader = [
        auth ? `Authorization=${auth}` : '',
        refresh ? `RefreshToken=${refresh}` : ''
    ].filter(Boolean).join(';');

    const template = await getTemplate(template_id, workspace.id, cookieHeader);
    if (!template) {
        notFound();
    }

    return <EditTemplateClient workspace={workspace} templateId={template_id} template={template} />;
}
