import React, { Suspense } from 'react';

import environments from '@app/configs/environments';
import fetchWithCookies from '@app/utils/fetchUtils';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';

import { FormDispatcher } from './_dispatcher/FormDispatcher';

export async function generateMetadata(props: { params: Promise<{ workspace_name: string; form_id: string }> }) {
    const params = await props.params;
    const workspaceResponse = await fetch(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces?workspace_name=' + params.workspace_name, { next: { revalidate: 300 } });
    const workspace = await workspaceResponse.json();
    const config = {
        method: 'GET'
    };
    const form = await fetchWithCookies(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + params.form_id + '?published=true', config);
    return {
        title: {
            default: params.workspace_name,
            absolute: form.title
        },
        description: form.welcomePage?.description || `This is ${params.workspace_name}'s form`,
        openGraph: {
            title: form.title,
            description: form.description,
            siteName: 'admin.bettercollected.com',
            images: [
                {
                    url: form?.welcomePage?.imageUrl,
                    width: 800,
                    height: 600
                }
            ],
            locale: 'en_US',
            type: 'website'
        }
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
        <FormWrapper workspaceName={params.workspace_name} formId={params.form_id}>
            {children}
        </FormWrapper>
    );
}

async function FormWrapper({ workspaceName, formId, children }: { workspaceName: string; formId: string; children: React.ReactNode }) {
    const workspaceResponse = await fetch(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces?workspace_name=' + workspaceName, { next: { revalidate: 300 } });
    const workspace = await workspaceResponse.json();

    const config = {
        method: 'GET'
    };

    const form = await fetchWithCookies(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + formId, config);

    return (
        <Suspense fallback={<FullScreenLoader />}>
            <FormDispatcher form={form}>{children}</FormDispatcher>
        </Suspense>
    );
}
