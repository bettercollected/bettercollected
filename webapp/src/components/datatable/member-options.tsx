import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { WorkspaceInvitationDto, WorkspaceMembersDto } from '@app/models/dtos/workspace-member-dto';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@app/shadcn/components/ui/alert-dialog';
import { Button } from '@app/shadcn/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@app/shadcn/components/ui/dropdown-menu';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useResendWorkspaceInvitationMutation } from '@app/store/workspaces/members-n-invitations-api';
import { Crown, Loader2, MoreHorizontal, RefreshCw, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';

import MakeBillingOwnerDialog, { billingOwnerBlocker } from '@app/components/member/make-billing-owner-dialog';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { WorkspaceRole, isBillingOwnerOf, memberRole } from '@app/models/enums/workspace-role';
import { memberRoles } from '@app/constants/locales/member-roles';
import { useAppSelector } from '@app/store/hooks';

interface IMemberOptionProps {
    member?: WorkspaceMembersDto;
    invitation?: WorkspaceInvitationDto;
    workspaceId: string;
}

export default function MemberOptions({ member, invitation }: IMemberOptionProps) {
    const { toast } = useToast();
    const [loading, setLoading] = useState(false);
    const [openConfirmDialog, setOpenConfirmDialog] = useState(false);
    const [selectedInvitation, setSelectedInvitation] = useState<WorkspaceInvitationDto | null>(null);
    const { t } = useTranslation();
    const { openModal } = useModal();
    const { can } = useWorkspacePermissions();
    const workspace = useAppSelector((state) => state.workspace);
    const [openBilling, setOpenBilling] = useState(false);
    // Every owner holds workspace.billing: they make another owner the
    // billing owner, and only they remove an owner.
    const callerIsOwner = can(WorkspacePermission.WORKSPACE_BILLING);
    const memberIsOwner = !!member && memberRole(member) === WorkspaceRole.OWNER;
    const canManageMembers = can(WorkspacePermission.MEMBERS_MANAGE) && (!memberIsOwner || callerIsOwner);
    const canMakeBillingOwner = !!member && callerIsOwner && memberIsOwner && !isBillingOwnerOf(member, workspace);
    const billingBlocked = member ? billingOwnerBlocker(workspace, memberRole(member)) : undefined;

    // Use the mutation hook
    const [resendWorkspaceInvitation] = useResendWorkspaceInvitationMutation();

    // nothing this user may do here (e.g. an Admin on an owner's row)
    if (!canManageMembers && !canMakeBillingOwner) return null;

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

            toast({ description: 'Invitation resent successfully!' });
        } catch (error: any) {
            toast({ description: `Error resending invitation: ${error.message}`, variant: 'destructive' });
        } finally {
            setLoading(false);
            handleCloseConfirmDialog();
        }
    };

    return (
        <>
            <AlertDialog open={openConfirmDialog} onOpenChange={setOpenConfirmDialog}>
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="h-8 w-8 p-0 hover:bg-black-200">
                            <span className="sr-only">Open menu</span>
                            <MoreHorizontal className="h-4 w-4" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent className="bg-white" align="end">
                        {invitation && canManageMembers && (
                            <DropdownMenuItem
                                onClick={() => handleResendInvitationClick(invitation)}
                                disabled={loading}
                                className="cursor-pointer"
                            >
                                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4 text-blue-600" />}
                                <span className={loading ? "text-gray-400" : "text-blue-600"}>{t(buttonConstant.resendInvitation)}</span>
                            </DropdownMenuItem>
                        )}
                        {canMakeBillingOwner && (
                            <DropdownMenuItem
                                onClick={() => setOpenBilling(true)}
                                disabled={!!billingBlocked}
                                title={billingBlocked ? t(billingBlocked) : undefined}
                                className="cursor-pointer"
                            >
                                <Crown className="mr-2 h-4 w-4" />
                                <span>{t(memberRoles.makeBillingOwner)}</span>
                            </DropdownMenuItem>
                        )}
                        {canManageMembers && (
                        <DropdownMenuItem
                            onClick={() => {
                                if (member) {
                                    openModal('DELETE_MEMBER', { member });
                                } else {
                                    openModal('DELETE_INVITATION', { invitation });
                                }
                            }}
                            className="cursor-pointer text-red-500 hover:text-red-500 focus:text-red-500"
                        >
                            <Trash2 className="mr-2 h-4 w-4 text-red-500" />
                            <span>{t(member ? buttonConstant.deleteMember : buttonConstant.removeInvitation)}</span>
                        </DropdownMenuItem>
                        )}
                    </DropdownMenuContent>
                </DropdownMenu>

                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('Are you sure?')}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {t('Do you really want to resend the invitation?')}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={loading} onClick={handleCloseConfirmDialog}>{t('No')}</AlertDialogCancel>
                        <AlertDialogAction disabled={loading} onClick={(e) => {
                            e.preventDefault();
                            handleConfirmResendInvitation();
                        }}>
                            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : t('Yes')}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
            {canMakeBillingOwner && member && <MakeBillingOwnerDialog open={openBilling} onOpenChange={setOpenBilling} member={member} />}
        </>
    );
}
