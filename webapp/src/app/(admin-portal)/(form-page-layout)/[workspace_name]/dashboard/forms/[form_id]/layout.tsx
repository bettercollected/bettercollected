import { notFound } from 'next/navigation';
import React, { Suspense } from 'react';
import FormDashboardLayoutClient from './_components/FormDashboardLayoutClient';

import environments from '@app/configs/environments';
import fetchWithCookies from '@app/utils/fetchUtils';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';

export async function generateMetadata(props: { params: Promise<{ workspace_name: string; form_id: string }> }) {
    const params = await props.params;
    const workspaceResponse = await fetch(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces?workspace_name=' + params.workspace_name, { next: { revalidate: 300 } });
    const workspace = await workspaceResponse.json();

    const config = {
        method: 'GET'
    };
    const form = await fetchWithCookies(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + params.form_id, config);
    return {
        title: {
            default: params.workspace_name,
            absolute: 'Edit | ' + form.title
        },
        description: form?.welcomePage?.description
    };
}

export default async function Layout(
    props: { children: React.ReactNode; params: Promise<{ form_id: string; workspace_name: string }> }
) {
    const params = await props.params;

    const {
        children
    } = props;

    return (
        <FormWrapper workspaceName={params.workspace_name} formId={params.form_id} params={params}>
            {children}
        </FormWrapper>
    );
}

async function FormWrapper({ workspaceName, formId, children, params }: { workspaceName: string; formId: string; children: React.ReactNode; params: { workspace_name: string; form_id: string } }) {
    const config = {
        method: 'GET'
    };

    const workspaceResponse = await fetch(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces?workspace_name=' + workspaceName, { next: { revalidate: 300 } });
    if (!workspaceResponse.ok) return notFound();
    const workspace = await workspaceResponse.json();

    const form = await fetchWithCookies(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + formId + '?published=true&draft=true', config);

    if (!form) return notFound();

    return (
        <Suspense fallback={<FullScreenLoader />}>
            <FormDashboardLayoutClient form={form} params={params}>
                {children}
            </FormDashboardLayoutClient>
        </Suspense>
    );
}
