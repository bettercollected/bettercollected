import { useState } from 'react';

import { useTranslation } from 'next-i18next';


import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { customize } from '@app/constants/locales/customize';
import { toastMessage } from '@app/constants/locales/toast-message';
import { validationMessage } from '@app/constants/locales/validation-message';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';

import { AppInput } from '@app/shadcn/components/ui/input';
import { useModal } from '../modal-views/context';
import { ICustomizeUrlModalProps } from '../modal-views/modals/customize-url-modal';


export default function CustomizeUrlUi({ url, form }: ICustomizeUrlModalProps) {
    const workspace = useAppSelector((state) => state.workspace);
    const { t } = useTranslation();
    const { toast } = useToast();
    const customUrl = form?.settings?.customUrl || '';
    const [slug, setSlug] = useState(customUrl);
    const [isError, setIsError] = useState(false);
    const { closeModal } = useModal();
    const dispatch = useAppDispatch();
    const [patchFormSettings, { isLoading }] = usePatchFormSettingsMutation();
    const handleOnchange = (e: any) => {
        setSlug(e.target.value.trim());
    };
    const slugRegex = /^(?![_-])(?!.*[_-]{2})[a-zA-Z0-9_-]+(?![_-])$/;

    const handleUpdate = async (event: any) => {
        event.preventDefault();

        const body = {
            customUrl: slug
        };
        if (!slug.match(slugRegex)) {
            setIsError(true);
        } else {
            const response: any = await patchFormSettings({
                workspaceId: workspace.id,
                formId: form.formId,
                body: body
            });
            if (response.data) {
                const settings = response.data.settings;
                dispatch(setFormSettings(settings));
                toast({ description: t(localesCommon.updated).toString() });
            } else {
                toast({ description: t(toastMessage.formSettingUpdateError).toString(), variant: 'destructive' });
                return response.error;
            }
            closeModal();
        }
    };
    return (
        <form onSubmit={handleUpdate} className="w-full">
            <p className="sh1">{t(customize.form.title)}</p>
            <ul className="list-disc  body4 ml-5 mt-4 !text-black-700 !mb-6">
                <li>{t(customize.form.point1)}</li>
                <li className="my-3">{t(customize.form.point2)}</li>
                <li>{t(customize.form.point3)}</li>
            </ul>
            <p className=" mb-3 body1  !leading-none">
                {t(localesCommon.slug)}
                <span className="text-red-500">*</span>
            </p>
            <AppInput id="title" value={slug} onChange={handleOnchange} />
            {!slug.match(slugRegex) && isError && <p className="body4 !text-red-500 h-[10px]">{t(validationMessage.slug)}</p>}
            <div className="px-10 py-6 gap-6 bg-blue-100 mt-8 md:w-[535px] w-full md:-ml-10 break-all">
                <p className="body1">{t(localesCommon.newLink)}</p>
                <p className="body3 ">
                    <span className="text-black-600"> {url}</span>/<span className="text-black-800 font-medium">{slug}</span>
                </p>
            </div>
            <div className="mt-5 flex flex-col w-full ">
                <Button size="medium" isLoading={isLoading} disabled={!slug.match(slugRegex)}>
                    {t(buttonConstant.updateNow)}
                </Button>
            </div>
        </form>
    );
}