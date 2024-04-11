'use client';

import { useSearchParams } from 'next/navigation';

import Form from '@app/views/organism/Form/Form';
import ReduxWrapperAppRouter from '@app/containers/ReduxWrapperAppRouter';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import SingleFormPage from '@app/pages/forms/v1/[id]';
import useWorkspace from '@app/store/jotai/workspace';
import environments from '@app/configs/environments';

export default function FormPage({ params }: { params: { form_id: string; workspace_name: string } }) {
    const searchParams = useSearchParams();
    const isPreviewMode = searchParams?.get('isPreview');
    const slug = params.form_id;

    const { standardForm } = useStandardForm();
    const { workspace } = useWorkspace();
    const hasCustomDomain = window.location.host !== environments.NEXT_PUBLIC_V1_CLIENT_ENDPOINT_DOMAIN;

    return (
        <ReduxWrapperAppRouter>
            {standardForm?.builderVersion === 'v2' && <Form isMobileView={!!isPreviewMode} />}
            {standardForm?.builderVersion !== 'v2' && <SingleFormPage hasCustomDomain={hasCustomDomain} slug={slug} form={standardForm} workspace={workspace} />}
        </ReduxWrapperAppRouter>
    );
}
