'use client';

import { useTranslation } from 'react-i18next';

import { memberRoles } from '@app/constants/locales/member-roles';
import { WorkspaceMembersDto } from '@app/models/dtos/workspace-member-dto';
import { WorkspaceRole, memberRole } from '@app/models/enums/workspace-role';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@app/shadcn/components/ui/alert-dialog';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { WORKSPACE_PERMISSIONS_TAG, workspacesApi } from '@app/store/workspaces/api';
import { useMakeBillingOwnerMutation } from '@app/store/workspaces/members-n-invitations-api';
import { setWorkspace } from '@app/store/workspaces/slice';
import { getFullNameFromUser } from '@app/utils/user-utils';

/**
 * Why this member can't become the billing owner, as a locale key, or
 * undefined when they can. Mirrors the backend: only another owner, never on
 * a personal (default) workspace, never on a paid plan (the plan is billed to
 * the current billing owner's account).
 */
export function billingOwnerBlocker(workspace: { default?: any; isPro?: boolean } | undefined, role?: WorkspaceRole): string | undefined {
    if (workspace?.default === true || workspace?.default === 'true') return memberRoles.billingPersonal;
    if (workspace?.isPro) return memberRoles.billingPaid;
    if (role !== WorkspaceRole.OWNER) return memberRoles.billingOnlyOwners;
    return undefined;
}

interface MakeBillingOwnerDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    member: WorkspaceMembersDto;
}

export default function MakeBillingOwnerDialog({ open, onOpenChange, member }: MakeBillingOwnerDialogProps) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const dispatch = useAppDispatch();
    const workspace = useAppSelector((state) => state.workspace);
    const [makeBillingOwner, { isLoading }] = useMakeBillingOwnerMutation();
    const blocked = billingOwnerBlocker(workspace, memberRole(member));

    const handleConfirm = async () => {
        const result: any = await makeBillingOwner({ workspaceId: workspace.id, userId: member.id });
        if (result?.error) {
            toast({ description: result.error?.data || t(memberRoles.billingFailed), variant: 'destructive' });
        } else {
            dispatch(setWorkspace({ ...workspace, ownerId: member.id }));
            dispatch(workspacesApi.util.invalidateTags([WORKSPACE_PERMISSIONS_TAG]));
            toast({ description: t(memberRoles.billingDone) });
        }
        onOpenChange(false);
    };

    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>{t(memberRoles.billingTitle, { name: getFullNameFromUser(member) })}</AlertDialogTitle>
                    <AlertDialogDescription>{blocked ? t(blocked) : t(memberRoles.billingDescription)}</AlertDialogDescription>
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
                        {t(memberRoles.makeBillingOwner)}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
}
