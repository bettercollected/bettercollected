import React from 'react';

import {useTranslation} from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import AddMember from '@Components/Common/Icons/Add-member';
import CopyIcon from '@Components/Common/Icons/Copy';
import DeleteIcon from '@Components/Common/Icons/Delete';
import EditIcon from '@Components/Common/Icons/Edit';
import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
import Eye from '@Components/Common/Icons/Eye';
import Pin from '@Components/Common/Icons/Pin';
import PrivateIcon from '@Components/Common/Icons/Private';
import PublicIcon from '@Components/Common/Icons/Public';
import ShareIcon from '@Components/Common/Icons/ShareIcon';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import {ListItemIcon, MenuItem} from '@mui/material';
import {toast} from 'react-toastify';

import {useModal} from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import {buttonConstant} from '@app/constants/locales/button';
import {localesCommon} from '@app/constants/locales/common';
import {formConstant} from '@app/constants/locales/form';
import {toastMessage} from '@app/constants/locales/toast-message';
import {toolTipConstant} from '@app/constants/locales/tooltip';
import {useCopyToClipboard} from '@app/lib/hooks/use-copy-to-clipboard';
import {StandardFormDto} from '@app/models/dtos/form';
import {WorkspaceDto} from '@app/models/dtos/workspaceDto';
import {setFormSettings} from '@app/store/forms/slice';
import {useAppDispatch} from '@app/store/hooks';
import {useGetAllRespondersGroupQuery, usePatchFormSettingsMutation} from '@app/store/workspaces/api';

interface IFormOptionsDropdownMenuProps {
    workspace: WorkspaceDto;
    form: StandardFormDto;
    hasCustomDomain: boolean;
    className?: string;
    redirectToDashboard?: boolean;
    showShare?: boolean;
}

export default function FormOptionsDropdownMenu({
                                                    workspace,
                                                    form,
                                                    hasCustomDomain,
                                                    className = '',
                                                    redirectToDashboard = false,
                                                    showShare = false
                                                }: IFormOptionsDropdownMenuProps) {
    const {openModal} = useModal();

    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
    const [currentActiveForm, setCurrentActiveForm] = React.useState<{
        form: StandardFormDto;
        shareUrl: string;
    } | null>(null);
    const {data} = useGetAllRespondersGroupQuery(workspace.id);

    const [_, copyToClipboard] = useCopyToClipboard();

    const dispatch = useAppDispatch();
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const {t} = useTranslation();
    const open = Boolean(anchorEl);

    const isCustomDomain = !!workspace.customDomain;

    const clientHost = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms`;
    const customDomain = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}/forms`;

    const handleShareUrl = () => {
        const slug = form.settings?.customUrl;
        let shareUrl = '';
        if (window && typeof window !== 'undefined') {
            const scheme = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://`;
            const domainHost = hasCustomDomain ? `${workspace.customDomain}/forms/${slug}` : `${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms/${slug}`;
            shareUrl = scheme + domainHost;
        }
        return shareUrl;
    };

    const handleClick = (event: React.MouseEvent<HTMLElement>, f: StandardFormDto) => {
        event.preventDefault();
        event.stopPropagation();
        setAnchorEl(event.currentTarget);
        const shareUrl = handleShareUrl();
        setCurrentActiveForm({form: f, shareUrl});
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
            toast(t(toastMessage.formSettingUpdateError).toString(), {type: 'error'});
            return response.error;
        }
    };

    const onPinnedChange = (event: any, f?: StandardFormDto) => {
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), {type: 'error', toastId: 'errorToast'});
        patchSettings({pinned: !f?.settings?.pinned}, f)
            .then((res) => {
            })
            .catch((e) => {
                toast(e.data, {type: 'error', toastId: 'errorToast'});
            });
    };

    const onPrivateChanged = (event: any, f?: StandardFormDto) => {
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), {type: 'error', toastId: 'errorToast'});
        const patchBody = {private: !f?.settings?.private, pinned: false};
        patchSettings(patchBody, f)
            .then((res) => {
            })
            .catch((e: any) => {
                toast(e.data, {type: 'error', toastId: 'errorToast'});
            });
    };

    const menuItemPinSettings = (
        <MenuItem sx={{paddingX: '20px', paddingY: '10px', height: '36px'}} className="body4 hover:bg-brand-100"
                  onClick={(e) => onPinnedChange(e, currentActiveForm?.form)}
                  disabled={!!currentActiveForm?.form?.settings?.private}>
            <ListItemIcon>
                <Pin width={20} height={20} className="text-black-900"/>
            </ListItemIcon>
            <span>{currentActiveForm?.form?.settings?.pinned ? t(formConstant.unPinForm) : t(formConstant.menu.pinForm)}</span>
        </MenuItem>
    );

    const menuItemShareSettings = (
        <MenuItem
            sx={{paddingX: '20px', paddingY: '10px', height: '36px'}}
            className="body4 hover:bg-brand-100"
            onClick={() =>
                openModal('SHARE_VIEW', {
                    url: currentActiveForm?.shareUrl,
                    title: t(formConstant.shareThisForm)
                })
            }
            disabled={!!currentActiveForm?.form?.settings?.private}
        >
            <ListItemIcon>
                <ShareIcon width={20} height={20}/>
            </ListItemIcon>
            <span>{t(localesCommon.share)}</span>
        </MenuItem>
    );

    const menuItemOpen = (
        <ActiveLink key={form.formId} href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`}>
            <MenuItem sx={{paddingX: '20px', paddingY: '10px', height: '36px'}} className="body4 hover:bg-brand-100">
                <ListItemIcon>
                    <Eye width={20} height={20} className="text-black-900"/>
                </ListItemIcon>
                {t(buttonConstant.open)}
            </MenuItem>
        </ActiveLink>
    );

    const menuItemEdit = (
        <ActiveLink key={'edit'} href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}/edit`}>
            <MenuItem sx={{paddingX: '20px', paddingY: '10px', height: '36px'}} className="body4 hover:bg-brand-100">
                <ListItemIcon>
                    <EditIcon width={20} height={20} className="text-black-900"/>
                </ListItemIcon>
                {t(buttonConstant.edit)}
            </MenuItem>
        </ActiveLink>
    );

    const menuItemCopy = (
        <MenuItem
            sx={{paddingX: '20px', paddingY: '10px', height: '36px'}}
            className="body4 hover:bg-brand-100"
            onClick={() => {
                if (currentActiveForm?.shareUrl) {
                    copyToClipboard(currentActiveForm?.shareUrl);
                    toast(t(toastMessage.formUrlCopied).toString(), {type: 'success'});
                }
            }}
        >
            <ListItemIcon>
                <CopyIcon width={20} height={20} className="text-black-900"/>
            </ListItemIcon>
            {t(buttonConstant.copyLink)}
        </MenuItem>
    );

    const menuItemCustomizeLink = (
        <MenuItem
            sx={{paddingX: '20px', paddingY: '10px', height: '36px'}}
            className="body4 hover:bg-brand-100"
            onClick={() => {
                openModal('CUSTOMIZE_URL', {
                    url: isCustomDomain ? customDomain : clientHost,
                    form: currentActiveForm?.form
                });
            }}
        >
            <ListItemIcon>
                <EditIcon width={20} height={20} className="text-black-900 stroke-[1.5]"/>
            </ListItemIcon>
            {t(buttonConstant.customizeLink)}
        </MenuItem>
    );
    const menuItemAddToGroup = (
        <Tooltip title={data?.length === 0 ? t(localesCommon.noGroupFound) : ''}>
            <span>
                <MenuItem
                    sx={{paddingX: '20px', paddingY: '10px', height: '36px'}}
                    disabled={data?.length === 0}
                    className="body4 hover:bg-brand-100"
                    onClick={() => {
                        openModal('ADD_GROUP_FORM', {
                            responderGroups: data,
                            form: currentActiveForm?.form
                        });
                    }}
                >
                    <ListItemIcon>
                        <AddMember width={20} height={20}/>
                    </ListItemIcon>
                    {t(buttonConstant.addToGroup)}
                </MenuItem>
            </span>
        </Tooltip>
    );

    return (
        <div className={className + ' !text-black-900'} onClick={(e) => e.preventDefault()}>
            <MenuDropdown width={210} onClick={(e: any) => handleClick(e, form)} id="form-menu"
                          menuTitle={t(toolTipConstant.formOptions)} menuContent={<EllipsisOption/>}
                          showExpandMore={false}>
                {menuItemOpen}
                {currentActiveForm?.form?.settings?.provider === 'self' && environments.ENABLE_FORM_BUILDER && menuItemEdit}
                {
                    form?.isPublished && <>
                        {!!currentActiveForm?.form?.settings?.private ? (
                            <Tooltip title={t(toolTipConstant.visibility)}>
                                <span>{menuItemPinSettings}</span>
                            </Tooltip>
                        ) : (
                            menuItemPinSettings
                        )}
                        {menuItemCopy}
                        {menuItemCustomizeLink}
                        {menuItemAddToGroup}
                        <MenuItem sx={{paddingX: '20px', paddingY: '10px', height: '36px'}}
                                  className="body4 hover:bg-brand-100"
                                  onClick={(e) => onPrivateChanged(e, currentActiveForm?.form)}>
                            <ListItemIcon>{!currentActiveForm?.form?.settings?.private ?
                                <PrivateIcon width={20} height={20}/> : <PublicIcon width={20} height={20}/>}</ListItemIcon>
                            <span>{t(!currentActiveForm?.form?.settings?.private ? formConstant.menu.makeFormPrivate : formConstant.menu.makeFormPublic)}</span>
                        </MenuItem>
                    </>
                }
                <MenuItem
                    onClick={() => openModal('DELETE_FORM_MODAL', {form: currentActiveForm?.form, redirectToDashboard})}
                    sx={{paddingX: '20px', paddingY: '10px', height: '36px'}} className="body4">
                    <ListItemIcon>
                        <DeleteIcon width={20} height={20} className="text-black-900 stroke-[1.5]"/>
                    </ListItemIcon>
                    <span>{t(formConstant.menu.deleteForm)}</span>
                </MenuItem>
            </MenuDropdown>
        </div>
    );
}
