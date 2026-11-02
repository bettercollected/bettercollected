'use client';

import React, { useEffect } from 'react';

import { usePathname } from 'next/navigation';

import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { StandardFormDto } from '@app/models/dtos/form';
import { resetSingleForm, selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

import FormShell from './form-shell';

export default function FormDashboardLayoutClient({ form, children, params }: { form: StandardFormDto; children: React.ReactNode; params: { workspace_name: string; form_id: string } }) {
    const dispatch = useAppDispatch();
    const pathname = usePathname();
    const storeForm = useAppSelector(selectForm);

    // Initial load set form
    useEffect(() => {
        dispatch(setForm(form));
        return () => {
            dispatch(resetSingleForm());
        };
    }, [form, dispatch]);

    if (pathname.endsWith('/edit')) {
        return <>{children}</>;
    }

    if (!form?.formId) {
        return <></>;
    }

    if (!storeForm?.formId) {
        return <FullScreenLoader />;
    }

    return (
        <FormShell form={storeForm} base={`/${params.workspace_name}/dashboard/forms/${params.form_id}`}>
            {children}
        </FormShell>
    );
}
