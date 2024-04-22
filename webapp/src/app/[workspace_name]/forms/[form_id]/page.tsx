'use client';

import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import ReduxWrapperAppRouter from '@app/containers/ReduxWrapperAppRouter';
import SingleFormPage from '@app/pages/forms/v1/[id]';
import { setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import FullScreenLoader from '@app/views/atoms/Loaders/FullScreenLoader';
import Form from '@app/views/organism/Form/Form';
import { useEffect, useRef } from 'react';

export default function FormPage({ params }: { params: { form_id: string; workspace_name: string } }) {
    const slug = params.form_id;

    return (
        <ReduxWrapperAppRouter>
            <FetchFormWrapper slug={slug} />
        </ReduxWrapperAppRouter>
    );
}

const FetchFormWrapper = ({ slug }: { slug: string }) => {
    const workspace = useAppSelector(selectWorkspace);
    const dispatch = useAppDispatch();
    const iframeRef = useRef(null);

    const { data, isLoading, error } = useGetWorkspaceFormQuery(
        {
            workspace_id: workspace.id,
            custom_url: slug,
            published: true
        },
        { skip: !workspace.id }
    );

    useEffect(() => {
        if (data?.formId) {
            dispatch(setForm(data));
        }
    }, [data]);

    const hasCustomDomain = window.location.host !== environments.FORM_DOMAIN;

    if (isLoading || error) {
        return <FullScreenLoader />;
    }
    const responderUri = data?.settings?.embedUrl || '';

    if (data?.importedFormId && data.settings?.showOriginalForm) {
        return (
            <>
                <div className="relative !min-h-screen">
                    <div className="!m-0' absolute bottom-0 left-0 right-0 top-0 !p-0">
                        <iframe ref={iframeRef} src={`${responderUri}?embedded=true`} width="100%" height="100%">
                            <Loader />
                        </iframe>
                    </div>
                </div>
            </>
        );
    }

    return (
        <div className="h-screen w-screen">
            {data?.builderVersion === 'v2' && <Form />}
            {data?.builderVersion !== 'v2' && <SingleFormPage hasCustomDomain={hasCustomDomain} slug={slug} form={data} workspace={workspace} />}
        </div>
    );
};
