"use client";
import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import DeleteIcon from '@app/components/Common/Icons/Common/Delete';
import EditIcon from '@app/components/Common/Icons/Common/Edit';
import EllipsisOption from '@app/components/Common/Icons/Common/EllipsisOption';
import AddMember from '@app/components/Common/Icons/Dashboard/Add-member';
import Eye from '@app/components/Common/Icons/Form/Eye';
import Pin from '@app/components/Common/Icons/Form/Pin';
import Tooltip from '@app/shadcn/components/ui/tooltip';
import { Copy, QrCode } from 'lucide-react';

import { LinkIcon } from '@app/components/icons/link-icon';
import { useModal } from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { toastMessage } from '@app/constants/locales/toast-message';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';
import { useDuplicateFormMutation, useGetAllRespondersGroupQuery, usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import getFormShareURL from '@app/utils/formUtils';
import { getEditFormURL } from '@app/utils/urlUtils';
import { validateFormOpen } from '@app/utils/validationUtils';

interface IFormOptionsDropdownMenuProps {
    workspace: WorkspaceDto;
    form: StandardFormDto;
    hasCustomDomain: boolean;
    className?: string;
    redirectToDashboard?: boolean;
    showShare?: boolean;
}

export default function FormOptionsDropdownMenu({ workspace, form, hasCustomDomain, className = '', redirectToDashboard = false, showShare = false }: IFormOptionsDropdownMenuProps) {
    const { openModal } = useModal();
    const { toast } = useToast();

    const [open, setOpen] = useState(false);
    const { data } = useGetAllRespondersGroupQuery(workspace.id);

    const [_, copyToClipboard] = useCopyToClipboard();

    const dispatch = useAppDispatch();
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const [duplicateForm] = useDuplicateFormMutation();
    const { t } = useTranslation();

    const isCustomDomain = !!workspace.customDomain;
    const isMobile = useIsMobile();

    const clientHost = `${window.PUBLIC_CONFIG?.FORM_DOMAIN.includes('localhost') ? 'http' : 'https'}://${window.PUBLIC_CONFIG?.FORM_DOMAIN}/${workspace.workspaceName}/forms`;
    const customDomain = `${window.PUBLIC_CONFIG?.FORM_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}/forms`;

    const isFormOpen = validateFormOpen(form?.settings?.formCloseDate);

    const handlePinSettings = (e: any) => {
        onPinnedChange(e, form);
        setOpen(false);
    };

    const patchSettings = async (body: any, f: StandardFormDto) => {
        const response: any = await patchFormSettings({
            workspaceId: workspace.id,
            formId: f.formId,
            body: body
        });
        if (response.data) {
            const settings = response.data.settings;
            dispatch(setFormSettings(settings));
        } else {
            toast({ description: t(toastMessage.formSettingUpdateError).toString(), variant: 'destructive' });
            return response.error;
        }
    };

    const onPinnedChange = (event: any, f?: StandardFormDto) => {
        if (!f) return toast({ description: t(toastMessage.formSettingUpdateError).toString(), variant: 'destructive' });
        patchSettings({ pinned: !f?.settings?.pinned }, f)
            .then((res) => { })
            .catch((e) => {
                toast({ description: e.data, variant: 'destructive' });
            });
    };

    const handleDuplicateFrom = () => {
        duplicateForm({ workspaceId: workspace.id, formId: form.formId })
            .then()
            .catch((e: any) => {
                toast({ description: 'Could not duplicate form', variant: 'destructive' });
            });
    };
    const menuItemPinSettings = (
        <li
            className={`flex items-center gap-2 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer ${!!form?.settings?.private || !!form?.settings?.hidden ? 'pointer-events-none opacity-50' : ''
                }`}
            onClick={handlePinSettings}
        >
            <div className="flex items-center justify-center">
                <Pin width={20} height={20} className="text-black-600" />
            </div>
            <span>{form?.settings?.pinned ? t(formConstant.unPinForm) : t(formConstant.menu.pinForm)}</span>
        </li>
    );

    const menuItemOpen = (
        <li className="list-none">
            <ActiveLink key={form.formId} href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`}>
                <div className="flex items-center gap-2 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer">
                    <div className="flex items-center justify-center">
                        <Eye width={20} height={20} className="text-black-600" />
                    </div>
                    {t(buttonConstant.open)}
                </div>
            </ActiveLink>
        </li>
    );

    const menuItemEdit = (
        <li className="list-none">
            <ActiveLink key={'edit'} href={getEditFormURL(workspace, form)}>
                <div className="flex items-center gap-2 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer">
                    <div className="flex items-center justify-center">
                        <EditIcon width={20} height={20} className="text-black-600" />
                    </div>
                    {t(buttonConstant.edit)}
                </div>
            </ActiveLink>
        </li>
    );

    const menuItemCopy = (
        <li
            className="flex items-center gap-2 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer"
            onClick={() => {
                const shareUrl = getFormShareURL(form, workspace);
                if (shareUrl) {
                    copyToClipboard(shareUrl);
                    toast({ description: t(toastMessage.formUrlCopied).toString() });
                    setOpen(false);
                }
            }}
        >
            <div className="flex items-center justify-center">
                <LinkIcon width={20} height={20} className="text-black-600" />
            </div>
            {t(buttonConstant.copyLink)}
        </li>
    );

    const menuItemCustomizeLink = (
        <li
            className="flex items-center gap-2 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer"
            onClick={() => {
                openModal('CUSTOMIZE_URL', {
                    url: isCustomDomain ? customDomain : clientHost,
                    form: form
                });
                setOpen(false);
            }}
        >
            <div className="flex items-center justify-center">
                <EditIcon width={20} height={20} className={'text-black-600'} />
            </div>
            {t(buttonConstant.customizeLink)}
        </li>
    );
    const menuItemAddToGroup = (
        <Tooltip label={data?.length === 0 ? t(localesCommon.noGroupFound) : ''}>
            <li
                className={`flex items-center gap-2 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer ${data?.length === 0 ? 'pointer-events-none opacity-50' : ''
                    }`}
                onClick={() => {
                    openModal('ADD_GROUP_FORM', {
                        responderGroups: data,
                        form: form
                    });
                    setOpen(false);
                }}
            >
                <div className="flex items-center justify-center">
                    <AddMember width={20} height={20} />
                </div>
                {t(buttonConstant.addToGroup)}
            </li>
        </Tooltip>
    );
    const menuItemGenerateQR = (
        <li
            className="flex items-center gap-2 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer"
            onClick={() => {
                openModal('GENERATE_QR', { form });
                setOpen(false);
            }}
        >
            <div className="flex items-center justify-center">
                <QrCode size={20} className={'text-black-600'} />
            </div>
            Generate QR
        </li>
    );

    const menuItemDuplicate = (
        <li
            className="flex items-center gap-2 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer"
            onClick={handleDuplicateFrom}
        >
            <div className="flex items-center justify-center">
                <Copy width={20} height={20} className={'text-black-600'} />
            </div>
            <span>Duplicate form</span>
        </li>
    );

    const menuItemDelete = (
        <li
            className="flex items-center gap-2 px-[20px] py-[10px] h-[36px] body4 hover:bg-brand-100 cursor-pointer"
            onClick={() => {
                openModal('DELETE_FORM_MODAL', { form, redirectToDashboard });
                setOpen(false);
            }}
        >
            <div className="flex items-center justify-center">
                <DeleteIcon width={20} height={20} className="text-black-600" />
            </div>
            <span>{t(formConstant.menu.deleteForm)}</span>
        </li>
    );

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                setOpen((open) => !open);
            }}>
                <div className={`${className} !text-black-900 cursor-pointer p-2 hover:bg-gray-100 rounded-md`}>
                    <EllipsisOption className="w-4 h-4" />
                </div>
            </PopoverTrigger>
            <PopoverContent
                className="w-[210px] p-0 bg-white"
                align="end"
                onClick={(e) => { e.stopPropagation(); setOpen(false); }}
                onInteractOutside={() => setOpen(false)}
            >
                <ul className="list-none m-0 p-0 flex flex-col">
                    {form?.isPublished && isFormOpen && (
                        <div className="w-full">
                            {!!form?.settings?.private || !!form?.settings?.hidden ? (
                                <Tooltip label={t(toolTipConstant.visibility)} side="top">
                                    <div>{menuItemPinSettings}</div>
                                </Tooltip>
                            ) : (
                                menuItemPinSettings
                            )}
                        </div>
                    )}
                    {menuItemOpen}
                    {form?.settings?.provider === 'self' && form?.builderVersion === 'v2' && !isMobile && menuItemEdit}
                    {form?.isPublished && !form?.settings?.hidden && isFormOpen && menuItemCopy}
                    {form?.isPublished && !form?.settings?.hidden && isFormOpen && menuItemCustomizeLink}
                    {form?.isPublished && !form?.settings?.hidden && isFormOpen && menuItemGenerateQR}
                    {form?.settings?.provider === 'self' && menuItemDuplicate}
                    {menuItemDelete}
                </ul>
            </PopoverContent>
        </Popover>
    );
}
