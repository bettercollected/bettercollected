'use client';

import { useSearchParams } from 'next/navigation';

import Form from '@app/views/organism/Form/Form';
import ReduxWrapperAppRouter from '@app/containers/ReduxWrapperAppRouter';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import SingleFormPage from '@app/pages/forms/[id]';
import useWorkspace from '@app/store/jotai/workspace';

export default function FormPage({ params }: { params: { formId: string; workspaceName: string } }) {
    const searchParams = useSearchParams();
    const isPreviewMode = searchParams?.get('isPreview');
    const { standardForm } = useStandardForm();
    const { workspace } = useWorkspace();

    return (
        <ReduxWrapperAppRouter>
            {standardForm?.builderVersion === 'v2' && <Form isMobileView={!!isPreviewMode} />}
            {standardForm?.builderVersion !== 'v2' && <SingleFormPage slug={standardForm?.settings?.customUrl} form={standardForm} workspace={workspace} />}
        </ReduxWrapperAppRouter>
    );
}
