import React, { useState } from 'react';
import { useTranslation } from 'next-i18next';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import Delete from '@Components/Common/Icons/Common/Delete';
import { MoreHoriz, Refresh } from '@mui/icons-material';
import { IconButton, ListItemIcon, Menu, MenuItem, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Button, Divider } from '@mui/material';
import { useModal } from '@app/Components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { WorkspaceInvitationDto, WorkspaceMembersDto } from '@app/models/dtos/WorkspaceMembersDto';
import { toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { useResendWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';

interface IMemberOptionProps {
    member?: WorkspaceMembersDto;
    invitation?: WorkspaceInvitationDto;
    workspaceId: string;
}

export default function MemberOptions({ member, invitation }: IMemberOptionProps) {
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [loading, setLoading] = useState(false);
    const [openConfirmDialog, setOpenConfirmDialog] = useState(false);
    const [selectedInvitation, setSelectedInvitation] = useState<WorkspaceInvitationDto | null>(null);
    const open = Boolean(anchorEl);
    const { t } = useTranslation();
    const { openModal } = useModal();

    // Use the mutation hook
    const [resendWorkspaceInvitation] = useResendWorkspaceInvitationMutation();

    const handleClick = (event: React.MouseEvent<HTMLElement>, f: any) => {
        event.preventDefault();
        event.stopPropagation();
        setAnchorEl(event.currentTarget);
    };

    const handleResendInvitationClick = (invitation: WorkspaceInvitationDto) => {
        setSelectedInvitation(invitation);
        setOpenConfirmDialog(true);
    };

    const handleCloseConfirmDialog = () => {
        setOpenConfirmDialog(false);
        setSelectedInvitation(null);
    };

    const handleConfirmResendInvitation = async () => {
        if (!selectedInvitation) return;

        setLoading(true);
        try {
            await resendWorkspaceInvitation({
                workspaceId: invitation?.workspaceId!,
                invitationToken: selectedInvitation.invitationToken
            }).unwrap();

            toast.success('Invitation resent successfully!');
        } catch (error: any) {
            toast.error(`Error resending invitation: ${error.message}`);
        } finally {
            setLoading(false);
            handleCloseConfirmDialog();
        }
    };

    return (
        <>
            <Tooltip title={t(toolTipConstant.Options)}>
                <IconButton
                    className="text-black-900 hover:bg-black-200 rounded-[4px] hover:rounded-[4px]"
                    onClick={(e) => handleClick(e, member)}
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
                {invitation && (
                    <MenuItem
                        onClick={() => handleResendInvitationClick(invitation)}
                        sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }}
                        className={`body4 ${loading ? 'cursor-not-allowed text-gray-400' : 'text-blue-600 hover:bg-blue-100'}`}
                        style={{ fontSize: '14px' }}
                        disabled={loading}
                    >
                        <ListItemIcon>{loading ? <CircularProgress size={24} /> : <Refresh className={`text-blue-600`} />}</ListItemIcon>
                        <span>{t(buttonConstant.resendInvitation)}</span>
                    </MenuItem>
                )}

                <MenuItem
                    onClick={() => {
                        if (member) {
                            openModal('DELETE_MEMBER', { member });
                        } else {
                            openModal('DELETE_INVITATION', { invitation });
                        }
                    }}
                    sx={{ paddingX: '20px', paddingY: '10px', height: '36px' }}
                    className="body4 !text-red-500 hover:bg-red-100"
                >
                    <ListItemIcon>
                        <Delete className="text-red-500" width={20} height={20} />
                    </ListItemIcon>
                    <span>{t(member ? buttonConstant.deleteMember : buttonConstant.removeInvitation)}</span>
                </MenuItem>
            </Menu>

            {/* Confirmation Dialog */}
            <Dialog
                open={openConfirmDialog}
                onClose={handleCloseConfirmDialog}
                aria-labelledby="confirm-dialog-title"
                PaperProps={{
                    sx: {
                        borderRadius: 2
                    }
                }}
            >
                <DialogTitle id="confirm-dialog-title" sx={{ borderBottom: '1px solid #ddd', paddingBottom: 2 }}>
                    {t('Are you sure?')}
                </DialogTitle>
                <Divider sx={{ marginY: 0 }} />
                <DialogContent sx={{ paddingTop: 2 }}>{t('Do you really want to resend the invitation?')}</DialogContent>

                <DialogActions sx={{ display: 'flex', justifyContent: 'center', gap: 2, paddingY: 3 }}>
                    <Button
                        onClick={handleCloseConfirmDialog}
                        sx={{
                            backgroundColor: '#4D4D4D',
                            color: 'white',
                            '&:hover': {
                                backgroundColor: '#1D1D1D'
                            },
                            fontSize: '14px',
                            padding: '10px 20px',
                            minWidth: '120px'
                        }}
                    >
                        {t('No')}
                    </Button>
                    <Button
                        onClick={handleConfirmResendInvitation}
                        sx={{
                            backgroundColor: '#007BFF', // Blue color for Yes button
                            color: 'white',
                            '&:hover': {
                                backgroundColor: '#0055ff' // Darker blue on hover
                            },
                            fontSize: '14px',
                            padding: '10px 20px',
                            minWidth: '120px',
                            position: 'relative'
                        }}
                        disabled={loading}
                        autoFocus
                    >
                        {loading ? <CircularProgress size={20} sx={{ color: 'white' }} /> : t('Yes')}
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
}
