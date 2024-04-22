import React, { Suspense } from 'react';

import environments from '@app/configs/environments';
import fetchWithCookies from '@app/utils/fetchUtils';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';

import { FormDispatcher } from './_dispatcher/FormDispatcher';

export async function generateMetadata({ params }: { params: { workspace_name: string; form_id: string } }) {
    const workspaceResponse = await fetch(process.env.API_ENDPOINT_HOST + '/workspaces?workspace_name=' + params.workspace_name);
    const workspace = await workspaceResponse.json();
    const config = {
        method: 'GET'
    };
    const form = await fetchWithCookies(environments.API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + params.form_id + '?published=true', config);
    return {
        title: {
            default: params.workspace_name,
            absolute: form.title
        },
        description: form.welcomePage.description || `This is ${params.workspace_name}'s form`,
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

export default function Layout({ children, params }: { children: React.ReactNode; params: { form_id: string; workspace_name: string } }) {
    return (
        <FormWrapper workspaceName={params.workspace_name} formId={params.form_id}>
            {children}
        </FormWrapper>
    );
}

async function FormWrapper({ workspaceName, formId, children }: { workspaceName: string; formId: string; children: React.ReactNode }) {
    const workspaceResponse = await fetch(process.env.API_ENDPOINT_HOST + '/workspaces?workspace_name=' + workspaceName);
    const workspace = await workspaceResponse.json();

    const config = {
        method: 'GET'
    };

    const form = await fetchWithCookies(environments.API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + formId, config);

    return (
        <Suspense fallback={<FullScreenLoader />}>
            <FormDispatcher form={form}>{children}</FormDispatcher>
        </Suspense>
    );
}
