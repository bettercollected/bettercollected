import AppButton from "@Components/Common/Input/Button/AppButton";
import React from "react";
import {useTranslation} from "next-i18next";
import {ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";
import {useRouter} from "next/router";
import {useAppSelector} from "@app/store/hooks";
import {selectWorkspace} from "@app/store/workspaces/slice";
import {IFormTemplateDto} from "@app/models/dtos/template";

interface IEditTemplateProps {
    templateId: string;
}

const EditTemplateButton = ({templateId}: IEditTemplateProps) => {
    const {t} = useTranslation();
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const handleOnClickEditButton = () => {
        router.push(`/${workspace.workspaceName}/templates/${templateId}/edit`);
    };
    return <AppButton variant={ButtonVariant.Secondary} onClick={handleOnClickEditButton}>
        Edit Template
    </AppButton>
}

export default EditTemplateButton