import React, { Suspense } from 'react';



import { FormDispatcher } from '@app/app/[workspaceName]/forms/[formId]/_dispatcher/FormDispatcher';
import environments from '@app/configs/environments';
import { store } from '@app/store/store';
import fetchWithCookies from '@app/utils/fetchUtils';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';


export default function Layout({
    children,
    params
}: {
    children: React.ReactNode;
    params: { formId: string; workspaceName: string };
}) {
    const workspaceId = store.getState().workspace.id;

    return (
        <FormWrapper workspaceName={params.workspaceName} formId={params.formId}>
            {children}
        </FormWrapper>
    );
}

async function FormWrapper({
    workspaceName,
    formId,
    children
}: {
    workspaceName: string;
    formId: string;
    children: React.ReactNode;
}) {
    console.log('third execution');

    const config = {
        method: 'GET'
    };
    const workspaceResponse = await fetch(
        process.env.API_ENDPOINT_HOST + '/workspaces?workspace_name=' + workspaceName
    );
    const workspace = await workspaceResponse.json()

    const form = await fetchWithCookies(
        environments.API_ENDPOINT_HOST +
            '/workspaces/' +
            workspace.id +
            '/forms/' +
            formId,
        config
    );

    return (
        <Suspense fallback={<FullScreenLoader />}>
            <FormDispatcher form={form}>{children}</FormDispatcher>
        </Suspense>
    );
}