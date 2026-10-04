
import { useTranslation } from 'react-i18next';


import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { placeHolder } from '@app/constants/locales/placeholder';
import { GroupInfoDto } from '@app/models/dtos/groups';
import { AppInput } from '@app/shadcn/components/ui/input';
import { Textarea } from '@app/shadcn/components/ui/textarea';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';


interface IGroupInfoProps {
    handleInput: (e: any) => void;
    groupInfo: GroupInfoDto;
}

export default function GroupInfo({ handleInput, groupInfo }: IGroupInfoProps) {
    const { t } = useTranslation();
    const { can } = useWorkspacePermissions();
    const canManageGroups = can(WorkspacePermission.MEMBERS_MANAGE);
    return (
        <div>
            {/*<p className="body1">{t(groupConstant.basicInformation)}</p>*/}
            <p className="h4-new !font-medium leading-none mb-2">
                {t(groupConstant.name)}
                <span className="text-red-800">*</span>
            </p>
            <AppInput className='w-full' disabled={!canManageGroups} value={groupInfo.name} id="name" placeholder={t(placeHolder.groupName)} onChange={handleInput} />
            <p className="h4-new leading-none mt-8 !font-medium mb-2">{t(localesCommon.description)}</p>
            <Textarea disabled={!canManageGroups} value={groupInfo.description} id="description" placeholder={t(placeHolder.description)} onChange={handleInput} className='bg-white rounded-md ring-none' />
        </div>
    );
}