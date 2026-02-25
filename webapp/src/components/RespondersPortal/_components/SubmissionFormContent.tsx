'use client';

import FormRenderer from '@app/components/Form/renderer/form-renderer';
import { useSubmissionContext } from './SubmissionContext';

export default function SubmissionFormContent() {
    const { data } = useSubmissionContext();
    if (!data) return null;
    return (
        <div className="mt-12 w-full">
            <FormRenderer form={data.form} response={data.response} isDisabled />
        </div>
    );
}
