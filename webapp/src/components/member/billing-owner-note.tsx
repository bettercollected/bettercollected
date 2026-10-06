'use client';

import { useTranslation } from 'react-i18next';

import { memberRoles } from '@app/constants/locales/member-roles';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { getFullNameFromUser } from '@app/utils/user-utils';

/** Whether the signed-in user is an owner of the current workspace but not
 *  its billing owner: the plan and the Stripe customer are someone else's. */
export function useIsCoOwner(): boolean {
    const workspace = useAppSelector((state) => state.workspace);
    const auth = useAppSelector(selectAuth);
    const { can } = useWorkspacePermissions();
    return can(WorkspacePermission.WORKSPACE_BILLING) && !!workspace?.ownerId && !!auth?.id && workspace.ownerId !== auth.id;
}

/**
 * "Billing is handled by <billing owner>", for an owner who isn't the billing
 * owner. Billing (Stripe customer, portal, checkout) is per person, so their
 * own billing links would never reach this workspace's plan. Renders nothing
 * for anyone else.
 */
export default function BillingOwnerNote({ className = '' }: { className?: string }) {
    const { t } = useTranslation();
    const workspace = useAppSelector((state) => state.workspace);
    const isCoOwner = useIsCoOwner();
    // owners hold members.manage, so they may read the members list
    const { data } = useGetWorkspaceMembersQuery({ workspaceId: workspace?.id }, { skip: !isCoOwner || !workspace?.id });

    if (!isCoOwner) return null;
    const billingOwner = data?.find((member) => member.billingOwner || member.id === workspace.ownerId);
    const name = billingOwner ? getFullNameFromUser(billingOwner)?.trim() || billingOwner.email : '';
    return (
        <p className={`text-xs text-black-600 ${className}`} data-testid="billing-owner-note">
            {name ? t(memberRoles.billingHandledBy, { name }) : t(memberRoles.billingHandledByOwner)}
        </p>
    );
}
