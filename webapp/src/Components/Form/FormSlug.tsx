import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Button } from '@app/shadcn/components/ui/button';

import { IFormCreateSlugFullModalViewProps } from '@app/Components/modal-views/full-screen-modals/create-form-slug-full-modal-view';
import { localesCommon } from '@app/constants/locales/common';
import { formPage } from '@app/constants/locales/form-page';
import { toastMessage } from '@app/constants/locales/toast-message';
import { validationMessage } from '@app/constants/locales/validation-message';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';


interface IFormSlugProps extends IFormCreateSlugFullModalViewProps {
    onSave: () => void;
}

export const FormSlug = ({ customSlug, link, onSave }: IFormSlugProps) => {
    const formId = customSlug;
    const { toast } = useToast();
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
                toast({ description: t(localesCommon.updated).toString() });
            } else {
                toast({ description: response?.error?.data || t(toastMessage.formSettingUpdateError).toString(), variant: 'destructive' });
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
                <AppInput value={slug} onChange={(event) => handleOnchange(event)} className="w-full" />
                {!slug.match(slugRegex) && isError && <p className="body4 !text-red-500 h-[10px]">{t(validationMessage.slug)}</p>}
            </div>
            <Button type={'submit'} onClick={handleUpdate} isLoading={isLoading} className={'w-[130px]'} variant="secondary">
                {t(formPage.linksSlugSaveChanges)}
            </Button>
        </div>
    );
};