'use client';

import { setForm } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useEffect } from 'react';

export function FormDispatcher({ form, children }: { form: any; children?: React.ReactNode }) {
    const { updateFormTheme } = useFormState();
    const dispatch = useAppDispatch();

    useEffect(() => {
        if (form.formId) {
            dispatch(setForm(form));
            updateFormTheme(form.theme);
            dispatch(setForm(form));
        }
    }, [form.formId]);

    return <>{children}</>;
}
