'use client';

import { useTranslation } from 'react-i18next';

import { memberRoles } from '@app/constants/locales/member-roles';
import { WorkspaceMembersDto } from '@app/models/dtos/workspace-member-dto';
import { WorkspaceRole, memberRole } from '@app/models/enums/workspace-role';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@app/shadcn/components/ui/alert-dialog';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { WORKSPACE_PERMISSIONS_TAG, workspacesApi } from '@app/store/workspaces/api';
import { useTransferWorkspaceOwnershipMutation } from '@app/store/workspaces/members-n-invitations-api';
import { setWorkspace } from '@app/store/workspaces/slice';
import { getFullNameFromUser } from '@app/utils/user-utils';

/**
 * Why ownership can't go to this member, as a locale key, or undefined when
 * it can. Mirrors the backend: only to an Admin, never a personal (default)
 * workspace, never one on a paid plan (the plan is billed to the owner).
 */
export function transferBlocker(workspace: { default?: any; isPro?: boolean } | undefined, role?: WorkspaceRole): string | undefined {
    if (workspace?.default === true || workspace?.default === 'true') return memberRoles.transferPersonal;
    if (workspace?.isPro) return memberRoles.transferPaid;
    if (role !== WorkspaceRole.ADMIN) return memberRoles.transferOnlyAdmins;
    return undefined;
}

interface TransferOwnershipDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    member: WorkspaceMembersDto;
}

export default function TransferOwnershipDialog({ open, onOpenChange, member }: TransferOwnershipDialogProps) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const dispatch = useAppDispatch();
    const workspace = useAppSelector((state) => state.workspace);
    const [transfer, { isLoading }] = useTransferWorkspaceOwnershipMutation();
    const blocked = transferBlocker(workspace, memberRole(member));

    const handleConfirm = async () => {
        const result: any = await transfer({ workspaceId: workspace.id, userId: member.id });
        if (result?.error) {
            toast({ description: result.error?.data || t(memberRoles.transferFailed), variant: 'destructive' });
        } else {
            dispatch(setWorkspace({ ...workspace, ownerId: member.id }));
            dispatch(workspacesApi.util.invalidateTags([WORKSPACE_PERMISSIONS_TAG]));
            toast({ description: t(memberRoles.transferDone) });
        }
        onOpenChange(false);
    };

    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>{t(memberRoles.transferTitle, { name: getFullNameFromUser(member) })}</AlertDialogTitle>
                    <AlertDialogDescription>{blocked ? t(blocked) : t(memberRoles.transferDescription)}</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel disabled={isLoading}>{t(memberRoles.cancel)}</AlertDialogCancel>
                    <AlertDialogAction
                        disabled={isLoading || !!blocked}
                        onClick={(e) => {
                            e.preventDefault();
                            handleConfirm();
                        }}
                    >
                        {t(memberRoles.transferOwnership)}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
}
