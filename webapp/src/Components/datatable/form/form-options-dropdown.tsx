import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import CopyIcon from '@Components/Common/Icons/Common/Copy';
import DeleteIcon from '@Components/Common/Icons/Common/Delete';
import EditIcon from '@Components/Common/Icons/Common/Edit';
import EllipsisOption from '@Components/Common/Icons/Common/EllipsisOption';
import AddMember from '@Components/Common/Icons/Dashboard/Add-member';
import Eye from '@Components/Common/Icons/Form/Eye';
import Pin from '@Components/Common/Icons/Form/Pin';
import { QrCode } from '@mui/icons-material';

import { LinkIcon } from '@app/Components/icons/link-icon';
import { useModal } from '@app/Components/modal-views/context';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import ActiveLink from '@app/Components/ui/links/active-link';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { toastMessage } from '@app/constants/locales/toast-message';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';
import { useDuplicateFormMutation, useGetAllRespondersGroupQuery, usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import getFormShareURL from '@app/utils/formUtils';
import { validateFormOpen } from '@app/utils/validationUtils';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { getEditFormURL } from '@app/utils/urlUtils';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';

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

    const clientHost = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms`;
    const customDomain = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}/forms`;

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
        <Tooltip title={data?.length === 0 ? t(localesCommon.noGroupFound) : ''}>
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
                <QrCode style={{ width: 20, height: 20 }} className={'text-black-600'} />
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
                <CopyIcon width={20} height={20} className={'text-black-600'} />
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
            <PopoverTrigger asChild>
                <div className={`${className} !text-black-900 cursor-pointer`} onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation()
                }}>
                    <EllipsisOption />
                </div>
            </PopoverTrigger>
            <PopoverContent
                className="w-[210px] p-0 bg-white"
                align="end"
                onClick={() => setOpen(false)}
                onInteractOutside={() => setOpen(false)}
            >
                <ul className="list-none m-0 p-0 flex flex-col">
                    {form?.isPublished && isFormOpen && (
                        <div className="w-full">
                            {!!form?.settings?.private || !!form?.settings?.hidden ? (
                                <Tooltip title={t(toolTipConstant.visibility)} placement={'top'}>
                                    <div>{menuItemPinSettings}</div>
                                </Tooltip>
                            ) : (
                                menuItemPinSettings
                            )}
                        </div>
                    )}
                    {menuItemOpen}
                    {form?.settings?.provider === 'self' && form?.builderVersion === 'v2' && environments.ENABLE_FORM_BUILDER && !isMobile && menuItemEdit}
                    {form?.isPublished && !form?.settings?.hidden && isFormOpen && menuItemCopy}
                    {form?.isPublished && !form?.settings?.hidden && isFormOpen && menuItemCustomizeLink}
                    {form?.isPublished && menuItemAddToGroup}
                    {form?.isPublished && !form?.settings?.hidden && isFormOpen && environments.ENABLE_FORM_QR && menuItemGenerateQR}
                    {form?.settings?.provider === 'self' && menuItemDuplicate}
                    {menuItemDelete}
                </ul>
            </PopoverContent>
        </Popover>
    );
}
