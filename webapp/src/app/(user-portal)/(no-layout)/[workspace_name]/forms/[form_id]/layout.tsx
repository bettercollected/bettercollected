import { WorkspaceDispatcher } from '@app/app/_dispatcher/workspace-dispatcher';
import environments from '@app/configs/environments';
import { getFormById, getWorkspaceByName } from '@app/lib/server/api';
import { Alert, AlertDescription, AlertTitle } from '@app/shadcn/components/ui/alert';
import { AlertCircle } from 'lucide-react';
import { Metadata } from 'next';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import React from 'react';

export async function generateMetadata({ params }: { params: Promise<{ workspace_name: string, form_id: string }> }): Promise<Metadata> {
    const { workspace_name, form_id } = await params;
    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace?.id) {
        return {
            title: 'Workspace Not Found'
        };
    }

    const form = await getFormById(workspace.id, form_id);

    if (!form) {
        return {
            title: 'Form Not Found'
        };
    }

    const title = form.title || 'Form';
    const description = form.description || 'Please fill out this form.';
    const images = form.coverImage ? [form.coverImage] : [];

    return {
        title,
        description,
        openGraph: {
            title,
            description,
            images,
            type: 'website'
        },
        twitter: {
            card: 'summary_large_image',
            title,
            description,
            images
        }
    };
}

export default async function CustomDomainLayout({ children, params }: { children: React.ReactNode, params: Promise<{ workspace_name: string, form_id: string }> }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasClientDomain = host === environments.FORM_DOMAIN;
    const { workspace_name } = await params;

    if (!hasClientDomain) {
        notFound();
    }

    const workspace = await getWorkspaceByName(workspace_name);

    if (!workspace?.id) {
        return (
            <div className="flex h-screen items-center justify-center p-4">
                <Alert variant="destructive" className="max-w-md">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>
                        Workspace not found or custom domain not configured properly.
                    </AlertDescription>
                </Alert>
            </div>
        );
    }

    return (
        <WorkspaceDispatcher workspace={workspace}>
            {children}
        </WorkspaceDispatcher>
    );
}
