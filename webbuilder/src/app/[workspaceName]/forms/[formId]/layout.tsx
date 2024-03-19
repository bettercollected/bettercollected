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

    // TODO: [Save in db] Set default layout if it's not saved in database (for now)
    const updatedFormFields: any = [];
    if (form && Array.isArray(form.fields)) {
        form.fields.forEach((field: any) => {
            if (field.type === 'slide') {
                const properties = field.properties;
                if (!properties?.layout) {
                    properties.layout = FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND;
                }

                field.properties = properties;
                updatedFormFields.push(field);
            }
        });
    }

    const newForm = { ...form, fields: updatedFormFields };

    return (
        <>
            <Suspense fallback={<FullScreenLoader />}>
                <FormDispatcher form={newForm}>{children}</FormDispatcher>
            </Suspense>
        </>
    );
}
