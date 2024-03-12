'use client';

import { useEffect } from 'react';

import { useStandardForm } from '@app/store/jotai/fetchedForm';

export function FormDispatcher({
    form,
    children
}: {
    form: any;
    children?: React.ReactNode;
}) {
    const { setStandardForm } = useStandardForm();
    useEffect(() => {
        if (form.formId) {
            setStandardForm(form);
        }
    }, [form.formId]);

    return <>{children}</>;
}
