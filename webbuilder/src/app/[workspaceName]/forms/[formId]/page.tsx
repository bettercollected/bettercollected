'use client';

import { useSearchParams } from 'next/navigation';

import Form from '@app/views/organism/Form/Form';

export default function FormPage({
    params
}: {
    params: { formId: string; workspaceName: string };
}) {
    const searchParams = useSearchParams();
    const isPreviewMode = searchParams.get('isPreview');

    return <Form isMobileView={!!isPreviewMode} />;
}
