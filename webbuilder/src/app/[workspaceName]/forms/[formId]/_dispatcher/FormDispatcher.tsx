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
        setStandardForm(form);
    }, [form]);

    return <>{children}</>;
}
