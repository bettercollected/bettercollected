import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { DeleteOutline, MoreHoriz, PushPin, PushPinOutlined, Share, Visibility, VisibilityOff } from '@mui/icons-material';
import { IconButton, ListItemIcon, Menu, MenuItem } from '@mui/material';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
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
            toast('Could not update this form setting!', { type: 'error' });
            return response.error;
        }
    };

    const onPinnedChange = (event: any, f?: StandardFormDto) => {
        if (!f) return toast('Could not update this form setting!', { type: 'error', toastId: 'errorToast' });
        patchSettings({ pinned: !f?.settings?.pinned }, f)
            .then((res) => {})
            .catch((e) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const onPrivateChanged = (event: any, f?: StandardFormDto) => {
        if (!f) return toast('Could not update this form setting!', { type: 'error', toastId: 'errorToast' });
        const patchBody = { private: !f?.settings?.private, pinned: false };
        patchSettings(patchBody, f)
            .then((res) => {})
            .catch((e: any) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const menuItemPinSettings = (
        <MenuItem className="body4 text-black-900" onClick={(e) => onPinnedChange(e, currentActiveForm?.form)} disabled={!!currentActiveForm?.form?.settings?.private}>
            <ListItemIcon>{currentActiveForm?.form?.settings?.pinned ? <PushPin fontSize="small" /> : <PushPinOutlined fontSize="small" />}</ListItemIcon>
            <span>{currentActiveForm?.form?.settings?.pinned ? 'Unpin form' : 'Pin form'}</span>
        </MenuItem>
    );

    const menuItemShareSettings = (
        <MenuItem className="body4 text-black-900" onClick={() => openModal('SHARE_VIEW', { url: currentActiveForm?.shareUrl, title: 'this form' })} disabled={!!currentActiveForm?.form?.settings?.private}>
            <ListItemIcon>
                <Share fontSize="small" />
            </ListItemIcon>
            <span>Share</span>
        </MenuItem>
    );

    return (
        <div className={className} onClick={(e) => e.preventDefault()}>
            <Tooltip title="Form options">
                <IconButton
                    className="rounded-[4px] text-black-900 hover:rounded-[4px] hover:bg-black-200"
                    onClick={(e) => handleClick(e, form)}
                    size="small"
                    aria-controls={open ? 'forms-menu' : undefined}
                    aria-haspopup="true"
                    aria-expanded={open ? 'true' : undefined}
                >
                    <MoreHoriz />
                </IconButton>
            </Tooltip>
            <Menu
                anchorEl={anchorEl}
                id="forms-menu"
                open={open}
                onClose={() => setAnchorEl(null)}
                onClick={() => setAnchorEl(null)}
                disableScrollLock={true}
                PaperProps={{
                    elevation: 0,
                    sx: {
                        width: 230,
                        overflow: 'hidden',
                        borderRadius: 1,
                        filter: 'drop-shadow(0px 0px 15px rgba(0,0,0,0.15))',
                        mt: 1.5,
                        '& .MuiAvatar-root': {
                            width: 32,
                            height: 32,
                            ml: -0.5,
                            mr: 2,
                            borderRadius: 1
                        },
                        '&:before': {
                            content: '""',
                            display: 'block',
                            position: 'absolute',
                            top: 0,
                            right: 14,
                            width: 10,
                            height: 10,
                            bgcolor: 'background.paper',
                            transform: 'translateY(-50%) rotate(45deg)',
                            zIndex: 0
                        }
                    }
                }}
                transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            >
                {!!currentActiveForm?.form?.settings?.private ? (
                    <Tooltip title="Visibility of the form should be public to pin it into the workspace.">
                        <div>{menuItemPinSettings}</div>
                    </Tooltip>
                ) : (
                    menuItemPinSettings
                )}
                <MenuItem className="body4 text-black-900" onClick={(e) => onPrivateChanged(e, currentActiveForm?.form)}>
                    <ListItemIcon>{currentActiveForm?.form?.settings?.private ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}</ListItemIcon>
                    <span>Update form visibility</span>
                </MenuItem>
                <Divider className="!my-0" />
                {!!currentActiveForm?.form?.settings?.private ? (
                    <Tooltip title="Visibility of the form should be public to pin it into the workspace.">
                        <div>{menuItemShareSettings}</div>
                    </Tooltip>
                ) : (
                    menuItemShareSettings
                )}

                <Divider className="!my-0" />
                <MenuItem onClick={() => openModal('DELETE_FORM_MODAL', { form: currentActiveForm?.form, redirectToDashboard })} className="body4">
                    <ListItemIcon>
                        <DeleteOutline fontSize="small" color="error" />
                    </ListItemIcon>
                    <span className="text-[#d32f2f]">Delete</span>
                </MenuItem>
            </Menu>
        </div>
    );
}
