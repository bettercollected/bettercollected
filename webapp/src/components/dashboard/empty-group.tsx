
import { useTranslation } from 'next-i18next';

import Tooltip from '@app/shadcn/components/ui/tooltip';
import { useBottomSheetModal } from '@app/components/Modals/Contexts/BottomSheetModalContext';
import { Button } from '@app/shadcn/components/ui/button';

import UserMore from '@app/components/icons/user-more';
import { groupConstant } from '@app/constants/locales/group';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';


export default function EmptyGroup({ formId }: { formId?: string }) {
    const { t } = useTranslation();
    const isAdmin = useAppSelector(selectIsAdmin);
    const { openBottomSheetModal } = useBottomSheetModal();
    return (
        <div className="my-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body2 text-center !font-medium sm:w-[252px] mt-7 mb-6">{t(groupConstant.title)}</p>
            <Tooltip label={!isAdmin ? t(toolTipConstant.noAccessToGroup) : ''}>
                <Button
                    disabled={!isAdmin}
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