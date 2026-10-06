import UserDetails from '@Components/common/user-details';
import { dataTableCustomStyles } from '@Components/datatable/datatable-styles';
import MemberOptions from '@Components/datatable/member-options';
import DataTable from 'react-data-table-component';
import { useTranslation } from 'react-i18next';

import RoleSelect from '@app/components/member/role-select';
import { memberRoles } from '@app/constants/locales/member-roles';
import { members } from '@app/constants/locales/members';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspaceMembersDto } from '@app/models/dtos/workspace-member-dto';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { WorkspaceRole, assignableRoles, isBillingOwnerOf, memberRole, roleLocale } from '@app/models/enums/workspace-role';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useUpdateWorkspaceMemberRoleMutation } from '@app/store/workspaces/members-n-invitations-api';
import { utcToLocalDate, utcToLocalTime } from '@app/utils/date-utils';

const customDataTableStyles = { ...dataTableCustomStyles };

customDataTableStyles.rows.style.backgroundColor = 'white';

function MemberRole({ member }: { member: WorkspaceMembersDto }) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const workspace = useAppSelector((state) => state.workspace);
    const auth = useAppSelector(selectAuth);
    const { can } = useWorkspacePermissions();
    const [updateRole, { isLoading }] = useUpdateWorkspaceMemberRoleMutation();
    const isBillingOwner = isBillingOwnerOf(member, workspace);
    const role = isBillingOwner ? WorkspaceRole.OWNER : memberRole(member);
    const isOwner = role === WorkspaceRole.OWNER;
    // Owners hold workspace.billing: only they make, demote or remove owners.
    const callerIsOwner = can(WorkspacePermission.WORKSPACE_BILLING);
    // The billing owner's role and one's own never change, and only an owner
    // changes another owner's; the backend refuses all three. A deleted
    // account keeps its role row but there is no one to change it for.
    const editable = can(WorkspacePermission.MEMBERS_MANAGE) && !isBillingOwner && (!isOwner || callerIsOwner) && member.id !== auth?.id && !member.accountDeleted;
    // A member the directory manages keeps the role their groups give, but an
    // owner can still make them an owner (the directory never changes owners).
    const offered = member.managedByDirectory ? (callerIsOwner ? [role, WorkspaceRole.OWNER].filter((r): r is WorkspaceRole => !!r) : []) : assignableRoles(callerIsOwner);

    // A member the SCIM directory manages: the role follows their groups at
    // the identity provider (the backend refuses a change, 409).
    const status = (
        <>
            {isBillingOwner && (
                <span className="text-[11px] font-medium text-black-500" data-testid={`billing-owner-${member.id}`}>
                    {t(memberRoles.billingOwner)}
                </span>
            )}
            {member.managedByDirectory && (
                <span className="text-[11px] font-medium text-black-500" data-testid={`managed-by-directory-${member.id}`}>
                    {t(members.managedByDirectory)}
                </span>
            )}
            {member.disabled && <span className="text-[11px] font-medium text-[#C43D3D]">{t(members.deactivated)}</span>}
        </>
    );

    if (!editable || offered.length === 0) {
        return (
            <div className="flex flex-col gap-0.5 py-1">
                <span title={role ? t(roleLocale(role).description) : undefined} data-testid={`member-role-${member.id}`}>
                    {role ? t(roleLocale(role).name) : t(memberRoles.unknownRole)}
                </span>
                {status}
            </div>
        );
    }

    const handleChange = async (next: WorkspaceRole) => {
        if (next === role) return;
        const result: any = await updateRole({ workspaceId: workspace.id, userId: member.id, role: next });
        if (result?.error) {
            toast({ description: result.error?.data || t(memberRoles.roleChangeFailed), variant: 'destructive' });
        } else {
            toast({ description: t(memberRoles.roleChanged) });
        }
    };

    return (
        <div className="flex flex-col gap-0.5 py-1">
            <RoleSelect value={role} roles={offered} onChange={handleChange} disabled={isLoading} ariaLabel={t(members.role)} />
            {status}
        </div>
    );
}

export default function MembersTable({ data }: any) {
    const workspace = useAppSelector((state) => state.workspace);
    const { can } = useWorkspacePermissions();
    const { t } = useTranslation();
    const canManageMembers = can(WorkspacePermission.MEMBERS_MANAGE);
    // every owner holds workspace.billing
    const isWorkspaceOwner = can(WorkspacePermission.WORKSPACE_BILLING);

    const dataTableResponseColumns: any = [
        {
            selector: (member: any) =>
                member.accountDeleted ? (
                    <span className="body3 text-black-600" data-testid={`member-deleted-${member.id}`}>
                        {t(memberRoles.deletedAccount)}
                    </span>
                ) : (
                    <UserDetails user={member} />
                ),
            name: t(members.member),
            minWidth: '300px',
            style: {
                color: '#101826',
                fontSize: '14px',
                fontWeight: 500,
                paddingLeft: '16px',
                paddingRight: '16px',
                overflow: 'auto hidden'
            }
        },

        {
            name: t(members.join),
            selector: (member: any) => (!!member?.joined ? `${utcToLocalDate(member?.joined)} - ${utcToLocalTime(member?.joined)}` : ''),
            style: {
                color: '#3A465A',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },
        {
            name: t(members.role),
            minWidth: '200px',
            cell: (member: any) => <MemberRole member={member} />,
            allowOverflow: true,
            style: {
                color: '#3A465A',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },
        {
            // the billing owner is neither removed nor made billing owner again
            cell: (member: any) => !isBillingOwnerOf(member, workspace) && (canManageMembers || isWorkspaceOwner) && <MemberOptions member={member} workspaceId={workspace?.id ?? ''} />,
            allowOverflow: true,
            button: true,
            width: '60px',
            style: {
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        }
    ];

    return (
        <>
            <DataTable className="mt-2 !overflow-auto p-0" columns={dataTableResponseColumns} data={data || []} customStyles={customDataTableStyles} highlightOnHover={false} pointerOnHover={false} />
        </>
    );
}
