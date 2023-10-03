import AppButton from "@Components/Common/Input/Button/AppButton";
import {ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";
import React, {useState} from "react";
import {
    IFormCreateSlugFullModalViewProps
} from "@app/components/modal-views/full-screen-modals/create-form-slug-full-modal-view";
import {setFormSettings} from "@app/store/forms/slice";
import {toast} from "react-toastify";
import {localesCommon} from "@app/constants/locales/common";
import {toastMessage} from "@app/constants/locales/toast-message";
import {usePatchFormSettingsMutation} from "@app/store/workspaces/api";
import {useAppDispatch, useAppSelector} from "@app/store/hooks";
import {useTranslation} from "next-i18next";
import AppTextField from "@Components/Common/Input/AppTextField";
import {validationMessage} from "@app/constants/locales/validation-message";

interface IFormSlugProps extends IFormCreateSlugFullModalViewProps {
    onSave: () => void
}

export const FormSlug = ({customSlug, link, onSave}: IFormSlugProps) => {
    const formId = customSlug;
    const [slug, setSlug] = useState(customSlug);
    const [isError, setIsError] = useState(false);
    const workspace = useAppSelector((state) => state.workspace);
    const [patchFormSettings, {isLoading}] = usePatchFormSettingsMutation();
    const dispatch = useAppDispatch();
    const {t} = useTranslation();

    const handleOnchange = (e: any) => {
        setIsError(false);
        setSlug(e.target.value.trim());
        if (!slug.match(slugRegex)) {
            setIsError(true);
        }
    };
    const slugRegex = /^(?=.*$)(?![_][-])(?!.*[_][-]{2})[a-zA-Z0-9_-]+(?<![_][-])$/;

    const handleUpdate = async (event: any) => {
        event.preventDefault();
        const body = {
            customUrl: slug
        };
        if (slug.match(slugRegex)) {
            const response: any = await patchFormSettings({
                workspaceId: workspace.id,
                formId: formId,
                body: body
            });
            if (response.data) {
                const settings = response.data.settings;
                dispatch(setFormSettings(settings));
                toast(t(localesCommon.updated).toString(), {type: 'success'});
            } else {
                toast(t(toastMessage.formSettingUpdateError).toString(), {type: 'error'});
                return response.error;
            }
            onSave();
        }
    };


    return <div className={"px-4 sm:px-20 md:px-[120px] w-full py-16 flex flex-col gap-12"}>
        <div className={'flex flex-col gap-1'}>
            <h1 className={"h2-new"}>Change Slug</h1>
            <p className={"text-sm font-normal text-black-700"}>Give your forms a touch of professionalism and ensure
                brand consistency by incorporating your custom slug</p>
        </div>
        <div className={"flex flex-col gap-2 !max-w-[660px]"}>
            <h1 className={"h4-new"}>Enter Slug</h1>
            <p className={"text-sm font-normal text-black-700"}>Avoid using spaces or special characters. Only “-” and
                “_” is accepted.</p>
            <p className={"text-sm font-normal text-black-700"}> {link}/<span
                className={"text-pink-500"}>{slug}</span></p>
            <AppTextField isError={isError}
                          value={slug} onChange={(event) => handleOnchange(event)}/>
            {!slug.match(slugRegex) && isError &&
                <p className="body4 !text-red-500 h-[10px]">{t(validationMessage.slug)}</p>}
        </div>
        <AppButton type={"submit"} onClick={handleUpdate} className={"w-[130px]"} variant={ButtonVariant.Secondary}>Save
            Changes</AppButton>
    </div>
}
