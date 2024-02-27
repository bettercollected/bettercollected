'use client';

import { useEffect } from 'react';

import { useDebounceValue } from 'usehooks-ts';

import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';

export default function AutoSaveForm({ formId }: { formId: string }) {
    const { formFields } = useFormFieldsAtom();
    const { formState } = useFormState();

    const combinedFormState = {
        ...formState,
        fields: formFields
    };
    const [debouncedForm] = useDebounceValue(combinedFormState, 500);

    useEffect(() => {
        if (debouncedForm.fields.length > 0) {
            const forms = JSON.parse(localStorage.getItem('forms') || '{}');
            const form = {
                formId,
                ...debouncedForm
            };
            forms[formId] = form;
            localStorage.setItem('forms', JSON.stringify(forms));
        }
    }, [debouncedForm]);

    return <></>;
}
