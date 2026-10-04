
import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import Tooltip from '@app/shadcn/components/ui/tooltip';

import UserMore from '@app/components/icons/user-more';
import { groupConstant } from '@app/constants/locales/group';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { useBottomSheetModal } from '@Components/modals/contexts/bottom-sheet-modal-context';


export default function EmptyGroup({ formId }: { formId?: string }) {
    const { t } = useTranslation();
    const { can } = useWorkspacePermissions();
    const canManageGroups = can(WorkspacePermission.MEMBERS_MANAGE);
    const { openBottomSheetModal } = useBottomSheetModal();
    return (
        <div className="my-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body2 text-center !font-medium sm:w-[252px] mt-7 mb-6">{t(groupConstant.title)}</p>
            <Tooltip label={!canManageGroups ? t(toolTipConstant.noAccessToGroup) : ''}>
                <Button
                    disabled={!canManageGroups}
                    onClick={() => {
                        openBottomSheetModal('CREATE_GROUP');
                    }}
                >
                    {t(groupConstant.createNewGroup.default)}
                </Button>
            </Tooltip>
        </div>
    );
}