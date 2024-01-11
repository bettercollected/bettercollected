import AppButton from "@Components/Common/Input/Button/AppButton";
import {ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";
import React from "react";
import {useTranslation} from "next-i18next";
import {toast} from "react-toastify";
import {selectWorkspace} from "@app/store/workspaces/slice";
import {useAppSelector} from "@app/store/hooks";
import {selectForm} from "@app/store/forms/slice";
import {useCreateTemplateFromFormMutation} from "@app/store/template/api";
import {useRouter} from "next/router";

interface IButtonProps {
    buttonType?: ButtonVariant;
}

const MakeTemplateButton = ({buttonType = ButtonVariant.Secondary}: IButtonProps) => {
    const {t} = useTranslation();
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
                toast('Created Successfully', {type: 'success'});
                router.replace(`/${workspace.workspaceName}/dashboard/templates`);
            } else {
                toast('Error Occurred').toString(), {type: 'error'};
            }
        } catch (err) {
            toast('Error Occurred').toString(), {type: 'error'};
        }
    }
    return <AppButton variant={buttonType} onClick={onClickMakeTemplateButton}>
        {t('TEMPLATE.BUTTONS.MAKE_TEMPLATE')}
    </AppButton>
}

export default MakeTemplateButton;