'use client';

import { useEffect, useMemo } from 'react';

import { useDebounceValue } from 'usehooks-ts';

import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { usePatchV2FormMutation } from '@app/store/redux/formApi';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { setForm } from '@app/store/forms/slice';

export default function AutoSaveForm({ formId }: { formId: string }) {
    const { formFields } = useFormFieldsAtom();
    const { formState } = useFormState();
    const workspace = useAppSelector(selectWorkspace);
    const { setStandardForm } = useStandardForm();

    const dispatch = useAppDispatch();
    const [patchV2Form] = usePatchV2FormMutation();

    const combinedFormState = useMemo(
        () => ({
            ...formState,
            fields: formFields
        }),
        [formFields, formState]
    );
    const [debouncedForm] = useDebounceValue(combinedFormState, 1000);

    const saveForm = async () => {
        const formData = new FormData();
        formData.append('form_body', JSON.stringify(debouncedForm));
        const requestData: any = {
            formId: formId,
            workspaceId: workspace.id,
            body: formData
        };
        const response: any = await patchV2Form(requestData);
        if (response.data) {
            setStandardForm(response.data);
            dispatch(setForm(response.data));
        }
    };

    useEffect(() => {
        if (debouncedForm.fields.length > 0) {
            workspace.id && saveForm();
        }
    }, [debouncedForm, workspace?.id]);

    return <></>;
}
