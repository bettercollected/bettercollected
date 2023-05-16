import React from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import Delete from '@Components/Common/Icons/Delete';
import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
import Eye from '@Components/Common/Icons/Eye';
import Pin from '@Components/Common/Icons/Pin';
import Share from '@Components/Common/Icons/Share';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { ListItemIcon, MenuItem } from '@mui/material';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { formsConstant } from '@app/constants/locales/forms';
import { localesGlobal } from '@app/constants/locales/global';
import { toastMessage } from '@app/constants/locales/toast-message';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';

interface IFormOptionsDropdownMenuProps {
    workspace: WorkspaceDto;
    form: StandardFormDto;
    hasCustomDomain: boolean;
    className?: string;
    redirectToDashboard?: boolean;
}

export default function FormOptionsDropdownMenu({ workspace, form, hasCustomDomain, className = '', redirectToDashboard = false }: IFormOptionsDropdownMenuProps) {
    const { openModal } = useModal();

    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
    const [currentActiveForm, setCurrentActiveForm] = React.useState<{ form: StandardFormDto; shareUrl: string } | null>(null);

    const dispatch = useAppDispatch();
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const { t } = useTranslation();
    const open = Boolean(anchorEl);

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
        setCurrentActiveForm({ form: f, shareUrl });
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
            toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error' });
            return response.error;
        }
    };

    const onPinnedChange = (event: any, f?: StandardFormDto) => {
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error', toastId: 'errorToast' });
        patchSettings({ pinned: !f?.settings?.pinned }, f)
            .then((res) => {})
            .catch((e) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const onPrivateChanged = (event: any, f?: StandardFormDto) => {
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error', toastId: 'errorToast' });
        const patchBody = { private: !f?.settings?.private, pinned: false };
        patchSettings(patchBody, f)
            .then((res) => {})
            .catch((e: any) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const menuItemPinSettings = (
        <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4 hover:bg-brand-100" onClick={(e) => onPinnedChange(e, currentActiveForm?.form)} disabled={!!currentActiveForm?.form?.settings?.private}>
            <ListItemIcon>
                <Pin width={20} height={20} />
            </ListItemIcon>
            <span>{currentActiveForm?.form?.settings?.pinned ? t(formsConstant.unPinForm) : t(formsConstant.menu.pinForm)}</span>
        </MenuItem>
    );

    const menuItemShareSettings = (
        <MenuItem
            sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }}
            className="body4 hover:bg-brand-100"
            onClick={() => openModal('SHARE_VIEW', { url: currentActiveForm?.shareUrl, title: t(formsConstant.shareThisForm) })}
            disabled={!!currentActiveForm?.form?.settings?.private}
        >
            <ListItemIcon>
                <Share width={20} height={20} />
            </ListItemIcon>
            <span>{t(localesGlobal.share)}</span>
        </MenuItem>
    );

    return (
        <div className={className} onClick={(e) => e.preventDefault()}>
            <MenuDropdown onClick={(e: any) => handleClick(e, form)} id="form-menu" menuTitle="Form options" menuContent={<EllipsisOption />} showExpandMore={false}>
                {!!currentActiveForm?.form?.settings?.private ? (
                    <Tooltip title={t(toolTipConstant.visibility)}>
                        <div>{menuItemPinSettings}</div>
                    </Tooltip>
                ) : (
                    menuItemPinSettings
                )}
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4 hover:bg-brand-100" onClick={(e) => onPrivateChanged(e, currentActiveForm?.form)}>
                    <ListItemIcon>
                        <Eye width={20} height={20} />
                    </ListItemIcon>
                    <span>{t(formsConstant.menu.visibility)}</span>
                </MenuItem>
                {!!currentActiveForm?.form?.settings?.private ? (
                    <Tooltip title={t(toolTipConstant.visibility)}>
                        <div>{menuItemShareSettings}</div>
                    </Tooltip>
                ) : (
                    menuItemShareSettings
                )}
                <MenuItem onClick={() => openModal('DELETE_FORM_MODAL', { form: currentActiveForm?.form, redirectToDashboard })} sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }} className="body4 hover:bg-red-100 !text-red-500">
                    <ListItemIcon>
                        <Delete width={20} height={20} />
                    </ListItemIcon>
                    <span>{t(formsConstant.menu.deleteForm)}</span>
                </MenuItem>
            </MenuDropdown>
        </div>
    );
}
