import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import { IFormCreateSlugFullModalViewProps } from '@app/components/modal-views/full-screen-modals/create-form-slug-full-modal-view';
import { localesCommon } from '@app/constants/locales/common';
import { formPage } from '@app/constants/locales/form-page';
import { toastMessage } from '@app/constants/locales/toast-message';
import { validationMessage } from '@app/constants/locales/validation-message';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';

interface IFormSlugProps extends IFormCreateSlugFullModalViewProps {
    onSave: () => void;
}

export const FormSlug = ({ customSlug, link, onSave }: IFormSlugProps) => {
    const formId = customSlug;
    const [slug, setSlug] = useState(customSlug);
    const [isError, setIsError] = useState(false);
    const workspace = useAppSelector((state) => state.workspace);
    const [patchFormSettings, { isLoading }] = usePatchFormSettingsMutation();
    const dispatch = useAppDispatch();
    const { t } = useTranslation();

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
                toast(t(localesCommon.updated).toString(), { type: 'success' });
            } else {
                toast(response?.error?.data || t(toastMessage.formSettingUpdateError).toString(), { type: 'error' });
                return response.error;
            }
            onSave();
        }
    };

    return (
        <div className={'w-full flex flex-col gap-12'}>
            <div className={'flex flex-col gap-1'}>
                <h1 className={'h2-new'}>{t(formPage.linksSlugTitle)}</h1>
                <p className={'text-sm font-normal text-black-700'}>{t(formPage.linksSlugDescription)}</p>
            </div>
            <div className={'flex flex-col gap-2 !max-w-[660px]'}>
                <h1 className={'h4-new'}>{t(formPage.linksSlugEnterSlug)}</h1>
                <p className={'text-sm font-normal text-black-700'}>{t(formPage.linksSlugAvoidUsing)}</p>
                <p className={'text-sm font-normal text-black-700'}>
                    {' '}
                    {link}/<span className={'text-pink-500'}>{slug}</span>
                </p>
                <AppTextField isError={isError} value={slug} onChange={(event) => handleOnchange(event)} />
                {!slug.match(slugRegex) && isError && <p className="body4 !text-red-500 h-[10px]">{t(validationMessage.slug)}</p>}
            </div>
            <AppButton type={'submit'} onClick={handleUpdate} isLoading={isLoading} className={'w-[130px]'} variant={ButtonVariant.Secondary}>
                {t(formPage.linksSlugSaveChanges)}
            </AppButton>
        </div>
    );
};
