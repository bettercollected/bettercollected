'use client';

import { useEffect } from 'react';
import { useFormState } from '@app/store/jotai/form';
import { useAppDispatch } from '@app/store/hooks';
import { setForm } from '@app/store/forms/slice';

export function FormDispatcher({ form, children }: { form: any; children?: React.ReactNode }) {
    const { updateFormTheme } = useFormState();
    const dispatch = useAppDispatch();

    useEffect(() => {
        if (form.formId) {
            dispatch(setForm(form));
            updateFormTheme(form.theme);
        }
    }, [form.formId]);

    return <>{children}</>;
}
