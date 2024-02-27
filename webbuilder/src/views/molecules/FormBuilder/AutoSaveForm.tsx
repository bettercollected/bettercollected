'use client';

import { useEffect } from 'react';

import { useDebounceValue } from 'usehooks-ts';

import useFormFieldsAtom from '@app/store/jotai/fieldSelector';

export default function AutoSaveForm({ formId }: { formId: string }) {
    const { formFields } = useFormFieldsAtom();

    const [debouncedFormFields] = useDebounceValue(formFields, 500);

    useEffect(() => {
        if (debouncedFormFields.length > 0) {
            const forms = JSON.parse(localStorage.getItem('forms') || '{}');
            const form = {
                formId,
                fields: debouncedFormFields
            };
            forms[formId] = form;
            localStorage.setItem('forms', JSON.stringify(forms));
        }
    }, [debouncedFormFields]);

    return <></>;
}
