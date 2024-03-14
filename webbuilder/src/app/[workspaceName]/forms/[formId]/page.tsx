'use client';

import { useEffect } from 'react';

import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import FormComponent from '@app/views/organism/Form/FormComponent';

export default function FormPage({
    params
}: {
    params: { formId: string; workspaceName: string };
}) {
    const { formResponse } = useFormResponse();

    return <FormComponent formResponse={formResponse} />;
}
