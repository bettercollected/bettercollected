import React, { Suspense } from 'react';

import { FormDispatcher } from '@app/app/[workspace_name]/forms/[form_id]/_dispatcher/FormDispatcher';
import environments from '@app/configs/environments';
import { store } from '@app/store/store';
import fetchWithCookies from '@app/utils/fetchUtils';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';

export async function generateMetadata({ params }: { params: { workspace_name: string; form_id: string } }) {
    const workspaceResponse = await fetch(process.env.API_ENDPOINT_HOST + '/workspaces?workspace_name=' + params.workspace_name);
    const workspace = await workspaceResponse.json();

    const config = {
        method: 'GET'
    };
    const form = await fetchWithCookies(environments.API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + params.form_id, config);
    return {
        title: {
            default: params.workspace_name,
            absolute: 'Edit | ' + form.title
        },
        description: form.welcomePage.description
    };
}

export default function Layout({ children, params }: { children: React.ReactNode; params: { form_id: string; workspace_name: string } }) {
    const workspaceId = store.getState().workspace.id;

    return (
        <FormWrapper workspaceName={params.workspace_name} formId={params.form_id}>
            {children}
        </FormWrapper>
    );
}

async function FormWrapper({ workspaceName, formId, children }: { workspaceName: string; formId: string; children: React.ReactNode }) {
    const config = {
        method: 'GET'
    };

    const workspaceResponse = await fetch(process.env.API_ENDPOINT_HOST + '/workspaces?workspace_name=' + workspaceName);
    const workspace = await workspaceResponse.json();

    const form = await fetchWithCookies(environments.API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + formId, config);

    return (
        <Suspense fallback={<FullScreenLoader />}>
            <FormDispatcher form={form}>{children}</FormDispatcher>
        </Suspense>
    );
}
