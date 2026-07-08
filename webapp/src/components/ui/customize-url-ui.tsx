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
    const isInvalid = !slug.match(slugRegex);
    return (
        <form onSubmit={handleUpdate} className="flex w-full flex-col gap-6">
            <div className="flex flex-col gap-1.5">
                <h2 className="text-black-900 text-lg font-semibold leading-snug">{t(customize.form.title)}</h2>
                <p className="text-black-600 text-sm leading-relaxed">Pick a short, memorable link for this form. Responses already collected aren&apos;t affected.</p>
            </div>

            <ul className="text-black-600 flex list-disc flex-col gap-1.5 pl-5 text-sm">
                <li>{t(customize.form.point1)}</li>
                <li>{t(customize.form.point2)}</li>
                <li>{t(customize.form.point3)}</li>
            </ul>

            <div className="flex flex-col gap-2">
                <label htmlFor="slug" className="text-black-700 text-sm font-medium">
                    {t(localesCommon.slug)}
                    <span className="text-[#C43D3D]"> *</span>
                </label>
                <AppInput id="slug" value={slug} onChange={handleOnchange} className={`!text-sm ${isError && isInvalid ? '!border-[#C43D3D]' : ''}`} />
                {isError && isInvalid && <p className="text-sm text-[#C43D3D]">{t(validationMessage.slug)}</p>}
            </div>

            <div className="border-black-300 bg-black-100 flex flex-col gap-1 rounded-lg border px-4 py-3">
                <span className="text-black-500 text-xs font-medium uppercase tracking-wide">{t(localesCommon.newLink)}</span>
                <p className="break-all text-sm">
                    <span className="text-black-600">{url}</span>/<span className="text-black-900 font-medium">{slug}</span>
                </p>
            </div>

            <Button size="medium" variant="primary" isLoading={isLoading} disabled={isInvalid}>
                {t(buttonConstant.updateNow)}
            </Button>
        </form>
    );
}