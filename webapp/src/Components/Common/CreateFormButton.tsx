import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';

import environments from '@app/configs/environments';
import { builderConstants } from '@app/constants/locales/form-builder';
import { setBuilderState } from '@app/store/form-builder/actions';
import { initBuilderState } from '@app/store/form-builder/builderSlice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateFormMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';


export default function CreateFormButton({ variant }: { variant?: ButtonVariant }) {
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const { t: builderTranslation } = useTranslation('builder');
    const [postCreateForm, { isLoading: posting }] = useCreateFormMutation();
    const dispatch = useAppDispatch();
    const onClickButton = async () => {
        const formData = new FormData();
        const postReq: any = {};
        postReq.title = initBuilderState.title;
        postReq.description = initBuilderState.description;
        postReq.fields = Object.values(initBuilderState.fields);
        postReq.buttonText = initBuilderState.buttonText;
        postReq.consent = [];
        postReq.settings = {};
        formData.append('form_body', JSON.stringify(postReq));
        const apiObj: any = { workspaceId: workspace.id, body: formData };
        const response: any = await postCreateForm(apiObj);

        if (response?.data) {
            router.push(`/${workspace?.workspaceName}/dashboard/forms/${response?.data?.formId}/edit`);
            dispatch(setBuilderState({ isFormDirty: false }));
        }
    };

    return (
        <>
            {environments.ENABLE_FORM_BUILDER && (
                <AppButton className="min-w-[160px]" variant={variant} onClick={onClickButton} isLoading={posting}>
                    {builderTranslation(builderConstants.createForm)}
                </AppButton>
            )}
        </>
    );
}