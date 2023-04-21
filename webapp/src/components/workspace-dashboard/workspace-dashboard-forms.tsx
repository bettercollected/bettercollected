import React from 'react';

import { DeleteOutline, MoreHoriz, PushPin, PushPinOutlined, Share, Visibility, VisibilityOff } from '@mui/icons-material';
import { Divider, IconButton, ListItemIcon, Menu, MenuItem, Tooltip } from '@mui/material';
import { toast } from 'react-toastify';

import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { EmptyImportFormIcon } from '@app/components/icons/empty-import-form-icon';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button/button';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IWorkspaceDashboardFormsProps {
    workspaceForms: any;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
}

export default function WorkspaceDashboardForms({ workspaceForms, workspace, hasCustomDomain }: IWorkspaceDashboardFormsProps) {
    const breakpoint = useBreakpoint();
    const { openModal } = useModal();

    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
    const [currentActiveForm, setCurrentActiveForm] = React.useState<{ form: StandardFormDto; shareUrl: string } | null>(null);

    const [patchFormSettings] = usePatchFormSettingsMutation();
    const dispatch = useAppDispatch();

    const open = Boolean(anchorEl);

    const forms = workspaceForms?.data?.items;

    const handleClick = (event: React.MouseEvent<HTMLElement>, { form, shareUrl }: { form: StandardFormDto; shareUrl: string }) => {
        event.preventDefault();
        event.stopPropagation();
        setAnchorEl(event.currentTarget);
        setCurrentActiveForm({ form, shareUrl });
    };

    const patchSettings = async (body: any, form: StandardFormDto) => {
        const response: any = await patchFormSettings({
            workspaceId: workspace.id,
            formId: form.formId,
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

    const onPinnedChange = (event: any, form?: StandardFormDto) => {
        if (!form) return toast('Could not update this form setting!', { type: 'error', toastId: 'errorToast' });
        patchSettings({ pinned: !form?.settings?.pinned }, form)
            .then((res) => {})
            .catch((e) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const onPrivateChanged = (event: any, form?: StandardFormDto) => {
        if (!form) return toast('Could not update this form setting!', { type: 'error', toastId: 'errorToast' });
        const patchBody = { private: !form?.settings?.private, pinned: false };
        patchSettings(patchBody, form)
            .then((res) => {})
            .catch((e: any) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    return (
        <div className="mb-10 w-full h-fit mt-5">
            {forms?.length === 0 ? (
                <div className="w-full h-full flex flex-col items-center justify-center bg-white rounded-[4px] py-[84px]">
                    <EmptyImportFormIcon className="mb-8" />
                    <p className="sh1 mb-4 !leading-none">Import your first form</p>
                    <p className="body4 mb-8 !leading-none">Import your Google Forms or Typeforms</p>
                    <Button onClick={() => openModal('IMPORT_FORMS')} size="medium">
                        Import Forms
                    </Button>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6 p-6 bg-white rounded-[4px]">
                    {forms?.length !== 0 &&
                        forms?.map((form: StandardFormDto) => {
                            const slug = form.settings?.customUrl;
                            let shareUrl = '';
                            if (window && typeof window !== 'undefined') {
                                const scheme = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://`;
                                const domainHost = hasCustomDomain ? `${workspace.customDomain}/forms/${slug}` : `${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms/${slug}`;
                                shareUrl = scheme + domainHost;
                            }
                            return (
                                <ActiveLink key={form.formId} href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`}>
                                    <div className="flex flex-col items-start justify-between h-full border-[1px] border-black-300 hover:border-brand-500 transition cursor-pointer rounded-[4px]">
                                        <div className="rounded-[4px] relative w-full px-4 py-6 flex min-h-28 flex-col gap-3 items-start justify-between bg-brand-100">
                                            <div className="rounded-[4px] h-[34px] w-[34px] relative">{form?.settings?.provider === 'typeform' ? <TypeformIcon /> : <GoogleFormIcon className="-ml-2" />}</div>
                                            <Tooltip title={form?.title || 'Untitled'} arrow placement="top-start" enterDelay={300}>
                                                <p className="body3 !not-italic leading-none">{['xs', '2xs', 'sm', 'md'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.title || 'Untitled', 15) : toEndDottedStr(form?.title || 'Untitled', 20)}</p>
                                            </Tooltip>
                                            <Tooltip className="absolute top-4 right-4" title={form?.settings?.private ? 'Hidden from your public workspace' : 'Public'} arrow placement="bottom-end" enterDelay={300}>
                                                <p className={`rounded-full leading-none text-[10px] px-2 flex py-1 items-center justify-center ${form?.settings?.private ? 'bg-brand-accent' : 'bg-green-600'} text-white`}>
                                                    {form?.settings?.private ? 'Hidden' : 'Public'}
                                                </p>
                                            </Tooltip>
                                            {form?.settings?.pinned && (
                                                <Tooltip className="absolute -top-2 left-0" title="Pinned to your public workspace view" arrow placement="top-start" enterDelay={300}>
                                                    <PushPin className="-rotate-45 text-brand-500" />
                                                </Tooltip>
                                            )}
                                        </div>
                                        <div className="relative flex justify-between items-center p-4 w-full">
                                            <p className="body4 !text-brand-600">{form?.responses} response</p>
                                            <Tooltip className="absolute right-4" title="Form options" arrow={true} placement="top-start" enterDelay={300}>
                                                <IconButton
                                                    className="rounded-[4px] text-black-900 hover:rounded-[4px] hover:bg-black-200"
                                                    onClick={(e) => handleClick(e, { form, shareUrl })}
                                                    size="small"
                                                    aria-controls={open ? 'forms-menu' : undefined}
                                                    aria-haspopup="true"
                                                    aria-expanded={open ? 'true' : undefined}
                                                >
                                                    <MoreHoriz />
                                                </IconButton>
                                            </Tooltip>
                                        </div>
                                    </div>
                                </ActiveLink>
                            );
                        })}
                </div>
            )}
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
                <MenuItem className="body4 text-black-900" onClick={(e) => onPinnedChange(e, currentActiveForm?.form)} disabled={!!currentActiveForm?.form?.settings?.private}>
                    <ListItemIcon>{currentActiveForm?.form?.settings?.pinned ? <PushPin fontSize="small" /> : <PushPinOutlined fontSize="small" />}</ListItemIcon>
                    <span>{currentActiveForm?.form?.settings?.pinned ? 'Unpin form' : 'Pin form'}</span>
                </MenuItem>
                <MenuItem className="body4 text-black-900" onClick={(e) => onPrivateChanged(e, currentActiveForm?.form)}>
                    <ListItemIcon>{currentActiveForm?.form?.settings?.private ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}</ListItemIcon>
                    <span>Update form visibility</span>
                </MenuItem>
                <Divider />
                <MenuItem className="body4 text-black-900" onClick={() => openModal('SHARE_VIEW', { url: currentActiveForm?.shareUrl, title: 'this form' })} disabled={!!currentActiveForm?.form?.settings?.private}>
                    <ListItemIcon>
                        <Share fontSize="small" />
                    </ListItemIcon>
                    <span>Share</span>
                </MenuItem>
                <Divider />
                <MenuItem onClick={() => openModal('DELETE_FORM_MODAL', { form: currentActiveForm?.form })} className="body4">
                    <ListItemIcon>
                        <DeleteOutline fontSize="small" color="error" />
                    </ListItemIcon>
                    <span className="text-[#d32f2f]">Delete</span>
                </MenuItem>
            </Menu>
        </div>
    );
}
