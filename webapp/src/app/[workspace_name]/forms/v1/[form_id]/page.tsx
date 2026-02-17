'use client';

import React from 'react';
import ReduxWrapperAppRouter from '@app/containers/ReduxWrapperAppRouter';
import SingleFormPage from '@app/Components/Form/v1/SingleFormPage';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useParams, useSearchParams } from 'next/navigation';
import { useGetWorkspaceFormQuery } from '@app/store/workspaces/api';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';

export default function FormV1Page() {
    return (
        <ReduxWrapperAppRouter>
            <FormWrapper />
        </ReduxWrapperAppRouter>
    );
}

function FormWrapper() {
    const params = useParams();
    const searchParams = useSearchParams();
    const slug = params?.form_id as string;
    const workspace = useAppSelector(selectWorkspace);
    const back = searchParams?.get('back') === 'true';

    const { data: form, isLoading, error } = useGetWorkspaceFormQuery(
        {
            workspace_id: workspace.id,
            custom_url: slug,
            published: true
        },
        { skip: !workspace.id || !slug }
    );

    if (isLoading) return <FullScreenLoader />;

    return (
        <SingleFormPage
            workspace={workspace}
            form={form}
            slug={slug}
            hasCustomDomain={false}
            back={back}
        />
    );
}
