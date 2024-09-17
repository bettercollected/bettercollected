import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useCreateTemplateFromFormMutation } from '@app/store/template/api';
import { selectWorkspace } from '@app/store/workspaces/slice';


interface IButtonProps {
    buttonType?: ButtonVariant;
}

const MakeTemplateButton = ({ buttonType = ButtonVariant.Secondary }: IButtonProps) => {
    const { t } = useTranslation();
    const router = useRouter();

    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);

    const [createFormAsTemplate] = useCreateTemplateFromFormMutation();

    const onClickMakeTemplateButton = async () => {
        try {
            const request = {
                workspace_id: workspace.id,
                form_id: form.formId
            };
            const response: any = await createFormAsTemplate(request);
            if (response?.data) {
                toast('Created Successfully', { type: 'success' });
                router.replace(`/${workspace.workspaceName}/dashboard/templates`);
            } else {
                toast('Error Occurred').toString(), { type: 'error' };
            }
        } catch (err) {
            toast('Error Occurred').toString(), { type: 'error' };
        }
    };
    return (
        <AppButton variant={buttonType} onClick={onClickMakeTemplateButton}>
            {t('TEMPLATE.BUTTONS.MAKE_TEMPLATE')}
        </AppButton>
    );
};

export default MakeTemplateButton;