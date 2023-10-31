import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';

import environments from '@app/configs/environments';
import { setBuilderState } from '@app/store/form-builder/actions';
import { initBuilderState } from '@app/store/form-builder/builderSlice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateTemplateMutation } from '@app/store/template/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function CreateTemplateButton({ variant }: { variant?: ButtonVariant }) {
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const { t: builderTranslation } = useTranslation('builder');

    const [postCreateTemplate, { isLoading: posting }] = useCreateTemplateMutation();
    const dispatch = useAppDispatch();
    const onClickButton = async () => {
        const templateData = new FormData();
        const postReq: any = {};
        postReq.title = initBuilderState.title;
        postReq.description = initBuilderState.description;
        postReq.fields = Object.values(initBuilderState.fields);
        postReq.buttonText = initBuilderState.buttonText;
        postReq.consent = [];
        postReq.settings = {};
        templateData.append('template_body', JSON.stringify(postReq));
        const apiObj: any = { workspace_id: workspace.id, body: templateData };
        const response: any = await postCreateTemplate(apiObj);

        if (response?.data) {
            router.push(`/${workspace?.workspaceName}/templates/${response?.data?.id}/edit`);
            dispatch(setBuilderState({ isFormDirty: false }));
        }
    };

    return (
        <>
            {environments.ENABLE_FORM_BUILDER && (
                <AppButton className="min-w-[160px]" variant={variant} onClick={onClickButton} isLoading={posting}>
                    Create Template
                </AppButton>
            )}
        </>
    );
}
