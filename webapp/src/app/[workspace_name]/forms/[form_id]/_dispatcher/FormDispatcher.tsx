'use client';

import { useEffect } from 'react';

import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormState } from '@app/store/jotai/form';

export function FormDispatcher({
    form,
    children
}: {
    form: any;
    children?: React.ReactNode;
}) {
    const { setStandardForm } = useStandardForm();
    const { updateFormTheme } = useFormState();

    useEffect(() => {
        if (form.formId) {
            setStandardForm(form);
            updateFormTheme(form.theme);
        }
    }, [form.formId]);

    return <>{children}</>;
}
