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
import { WorkspaceRole, memberRole, roleLocale } from '@app/models/enums/workspace-role';
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
    const role = memberRole(member);
    const isOwner = role === WorkspaceRole.OWNER || workspace?.ownerId === member.id;
    // The owner's role and one's own never change; the backend refuses both.
    const editable = can(WorkspacePermission.MEMBERS_MANAGE) && !isOwner && member.id !== auth?.id;

    if (!editable) {
        const shown = isOwner ? WorkspaceRole.OWNER : role;
        return (
            <span title={shown ? t(roleLocale(shown).description) : undefined} data-testid={`member-role-${member.id}`}>
                {shown ? t(roleLocale(shown).name) : t(memberRoles.unknownRole)}
            </span>
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

    return <RoleSelect value={role} onChange={handleChange} disabled={isLoading} ariaLabel={t(members.role)} />;
}

export default function MembersTable({ data }: any) {
    const workspace = useAppSelector((state) => state.workspace);
    const { can } = useWorkspacePermissions();
    const { t } = useTranslation();
    const canManageMembers = can(WorkspacePermission.MEMBERS_MANAGE);
    const isWorkspaceOwner = can(WorkspacePermission.WORKSPACE_BILLING);

    const dataTableResponseColumns: any = [
        {
            selector: (member: any) => <UserDetails user={member} />,
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
            cell: (member: any) => workspace?.ownerId !== member.id && (canManageMembers || isWorkspaceOwner) && <MemberOptions member={member} workspaceId={workspace?.id ?? ''} />,
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
