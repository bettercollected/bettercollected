'use client';

import { useEffect } from 'react';

import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormState } from '@app/store/jotai/form';
import { useAppDispatch } from '@app/store/hooks';
import { setForm } from '@app/store/forms/slice';

export function FormDispatcher({ form, children }: { form: any; children?: React.ReactNode }) {
    const { setStandardForm } = useStandardForm();
    const { updateFormTheme } = useFormState();
    const dispatch = useAppDispatch();

    useEffect(() => {
        if (form.formId) {
            setStandardForm(form);
            dispatch(setForm(form));
            updateFormTheme(form.theme);
        }
    }, [form.formId]);

    return <>{children}</>;
}
