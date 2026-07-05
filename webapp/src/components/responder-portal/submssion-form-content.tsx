'use client';

import FormRenderer from '@Components/form/form-renderer';
import { useSubmissionContext } from './submission-context';

export default function SubmissionFormContent() {
    const { data } = useSubmissionContext();
    if (!data) return null;
    return (
        <div className="mt-12 w-full">
            <FormRenderer form={data.form} response={data.response} isDisabled />
        </div>
    );
}
