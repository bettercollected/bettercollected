
import DeleteDropDown from '@app/components/ui/delete-dropdown';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

interface IMemberCardProps {
    email: string;
    onDeleteClick: () => void;
    bg?: string;
}

export default function MemberCard({ email, onDeleteClick, bg = 'white' }: IMemberCardProps) {
    const { can } = useWorkspacePermissions();
    const canManageGroups = can(WorkspacePermission.MEMBERS_MANAGE);

    return (
        <div className={`flex justify-between body4 bg-${bg} px-4  rounded py-3 items-center !text-black-800`}>
            <span>{email}</span>
            {canManageGroups && <DeleteDropDown onDropDownItemClick={onDeleteClick} className="z-[2000000000]" />}
        </div>
    );
}