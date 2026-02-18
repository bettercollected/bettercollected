import React from 'react';
import { notFound } from 'next/navigation';
import environments from '@app/configs/environments';
import SingleTemplateClient from './SingleTemplateClient';

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

export default async function TemplatePage({ params }: { params: { workspace_name: string, template_id: string } }) {
    const { workspace_name, template_id } = await params;
    
    const workspace = await getWorkspaceByName(workspace_name);
    if (!workspace?.id) {
        notFound();
    }

    return <SingleTemplateClient workspace={workspace} templateId={template_id} />;
}
