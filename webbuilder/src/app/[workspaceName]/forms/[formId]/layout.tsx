import React, { Suspense } from 'react';

import environments from '@app/configs/environments';
import { FormSlideLayout } from '@app/models/enums/form';
import { store } from '@app/store/store';
import fetchWithCookies from '@app/utils/fetchUtils';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';

import { FormDispatcher } from './_dispatcher/FormDispatcher';

export default function Layout({
    children,
    params
}: {
    children: React.ReactNode;
    params: { formId: string };
}) {
    const workspaceId = store.getState().workspace.id;

    return (
        <>
            <FormWrapper workspaceId={workspaceId} formId={params.formId}>
                {children}
            </FormWrapper>
        </>
    );
}

async function FormWrapper({
    workspaceId,
    formId,
    children
}: {
    workspaceId: string;
    formId: string;
    children: React.ReactNode;
}) {
    const config = {
        method: 'GET'
    };

    const form = await fetchWithCookies(
        environments.API_ENDPOINT_HOST +
            '/workspaces/' +
            workspaceId +
            '/forms/' +
            formId,
        config
    );


    return (
        <>
            <Suspense fallback={<FullScreenLoader />}>
                <FormDispatcher form={form}>{children}</FormDispatcher>
            </Suspense>
        </>
    );
}
