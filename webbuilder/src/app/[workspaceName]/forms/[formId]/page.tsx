'use client';


import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import FormComponent from '@app/views/organism/Form/FormComponent';

export default function FormPage({
    params
}: {
    params: { formId: string; workspaceName: string };
}) {

    return <FormComponent  />;
}
