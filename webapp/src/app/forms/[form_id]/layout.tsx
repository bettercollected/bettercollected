import { WorkspaceDispatcher } from '@app/app/[workspace_name]/_dispatcher/WorkspaceDispatcher';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';
import React, { Suspense } from 'react';

export async function generateMetadata() {
    const domain = headers().get('host') || '';
    const workspaceResponse = await fetch(process.env.API_ENDPOINT_HOST + '/workspaces?custom_domain=' + domain);
    const workspace = await workspaceResponse.json();

    return {
        title: workspace.title,
        description: `${workspace.title}'s form`,

        openGraph: {
            title: workspace.title,
            description: workspace.description,
            siteName: 'admin.bettercollected.com',
            images: [
                {
                    url: workspace.bannerImage,
                    width: 800,
                    height: 600
                }
            ],
            locale: 'en_US',
            type: 'website'
        }
    };
}

const getWorkspaceByDomain = async (domain: string) => {
    const workspaceResponse = await fetch(process.env.API_ENDPOINT_HOST + '/workspaces?custom_domain=' + domain);

    const workspace = await workspaceResponse.json();
    return workspace;
};

async function WorkspaceWrapper({ domain, children }: { domain: string; children: React.ReactNode }) {
    const workspace = await getWorkspaceByDomain(domain);

    if (!workspace.id) {
        return notFound();
    }

    return (
        <Suspense fallback={<FullScreenLoader />}>
            <WorkspaceDispatcher workspace={workspace}>{children}</WorkspaceDispatcher>
        </Suspense>
    );
}

export default function Layout({ children }: { children: React.ReactNode }) {
    const domain = headers().get('host') || '';
    return <WorkspaceWrapper domain={domain}>{children}</WorkspaceWrapper>;
}
