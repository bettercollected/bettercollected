'use client';

import { useEffect, useMemo, useRef } from 'react';

import { useDebounceValue } from 'usehooks-ts';

import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { usePatchV2FormMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function AutoSaveForm({ formId }: { formId: string }) {
    const { formFields } = useFormFieldsAtom();
    const { formState } = useFormState();
    const workspace = useAppSelector(selectWorkspace);

    const dispatch = useAppDispatch();
    const form = useAppSelector(selectForm);
    const [patchV2Form] = usePatchV2FormMutation();

    const combinedFormState = useMemo(
        () => ({
            ...formState,
            welcomePage: {
                ...formState.welcomePage,
                title: formState.title
            },
            fields: formFields
        }),
        [formFields, formState]
    );
    const [debouncedForm] = useDebounceValue(combinedFormState, 1000);

    // Serialized snapshot of the last state we consider "saved", plus the time
    // the editor mounted. Together these stop the editor from auto-saving while
    // it hydrates the loaded form on open: opening a form populates the builder
    // state from the loaded data (across a couple of renders, since form state
    // and fields are separate atoms), which must not be mistaken for user edits.
    const lastSavedBodyRef = useRef<string | null>(null);
    const mountedAtRef = useRef<number>(Date.now());
    // Window during which state changes are treated as hydration, not edits.
    // Comfortably covers the 1s debounce plus a settle; user edits after this
    // (or a later edit) still save.
    const HYDRATION_WINDOW_MS = 2500;

    const saveForm = async (serializedForm: string) => {
        const formData = new FormData();
        formData.append('form_body', serializedForm);
        const requestData: any = {
            formId: formId,
            workspaceId: workspace.id,
            body: formData
        };
        const response: any = await patchV2Form(requestData);
        if (response.data) {
            dispatch(setForm({ ...response.data, settings: form.settings }));
        }
    };

    useEffect(() => {
        if (!workspace?.id || debouncedForm.fields.length === 0) return;

        const body = JSON.stringify(debouncedForm);

        // While the loaded form is still hydrating, keep the baseline in sync
        // instead of saving, so opening a form never triggers a write.
        if (Date.now() - mountedAtRef.current < HYDRATION_WINDOW_MS) {
            lastSavedBodyRef.current = body;
            return;
        }

        // Past hydration: save only when the content actually changed.
        if (body === lastSavedBodyRef.current) return;

        lastSavedBodyRef.current = body;
        saveForm(body);
    }, [debouncedForm, workspace?.id]);

    return <></>;
}
