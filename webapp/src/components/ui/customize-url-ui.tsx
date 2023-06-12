import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';
import { PersistPartial } from 'redux-persist/es/persistReducer';

import { buttonConstant } from '@app/constants/locales/button';
import { customize } from '@app/constants/locales/customize';
import { localesGlobal } from '@app/constants/locales/global';
import { toastMessage } from '@app/constants/locales/toast-message';
import { validationMessage } from '@app/constants/locales/validation-message';
import { StandardFormDto } from '@app/models/dtos/form';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';

import { useModal } from '../modal-views/context';
import { ICustomizeUrlModalProps } from '../modal-views/modals/customize-url-modal';
import Button from './button/button';

export default function CustomizeUrlUi({ description, url, form }: ICustomizeUrlModalProps) {
    const workspace = useAppSelector((state) => state.workspace);
    const { t } = useTranslation();
    const customUrl = form?.settings?.customUrl || '';
    const [slug, setSlug] = useState(customUrl);
    const [isError, setError] = useState(false);
    const { closeModal } = useModal();
    const dispatch = useAppDispatch();
    const [patchFormSettings, { isLoading }] = usePatchFormSettingsMutation();
    const handleOnchange = (e: any) => {
        setSlug(e.target.value);
    };

    const handleUpdate = async () => {
        const body = {
            customUrl: slug
        };
        if (slug === '') {
            setError(true);
        } else {
            const response: any = await patchFormSettings({
                workspaceId: workspace.id,
                formId: form.formId,
                body: body
            });
            if (response.data) {
                const settings = response.data.settings;
                dispatch(setFormSettings(settings));
                toast(t(localesGlobal.updated).toString(), { type: 'success' });
            } else {
                toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error' });
                return response.error;
            }
            closeModal();
        }
    };
    return (
        <div className="w-full">
            <p className="sh1 ">{t(customize.url)}</p>
            <p className="pt-6  pb-8 !text-black-600">{description}</p>
            <p className=" mb-3 body1  !leading-none">
                {t(localesGlobal.slug)}
                <span className="text-red-500">*</span>
            </p>
            <TextField
                InputProps={{
                    sx: {
                        height: '46px',
                        borderColor: '#0764EB !important'
                    }
                }}
                id="title"
                error={slug === '' && isError}
                className="w-full"
                value={slug}
                onChange={handleOnchange}
            />
            {slug === '' && isError && <p className="body4 !text-red-500 mt-2 h-[10px]">{t(validationMessage.slug)}</p>}
            <div className="px-10 py-6 gap-6 bg-blue-100 mt-8 md:w-[454px] w-full md:-ml-10 break-all">
                <p className="body1">{t(localesGlobal.newLink)}</p>
                <p className="body3 ">
                    <span className="text-black-600"> {url}</span>/<span className="text-black-800 font-medium">{slug}</span>
                </p>
            </div>
            <div className="mt-5 flex justify-end">
                <Button onClick={handleUpdate} isLoading={isLoading}>
                    {t(buttonConstant.updateUrl)}
                </Button>
            </div>
        </div>
    );
}
