import React from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';

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
            <Tooltip title={!isAdmin ? t(toolTipConstant.noAccessToGroup) : ''}>
                <AppButton
                    disabled={!isAdmin}
                    onClick={() => {
                        openBottomSheetModal('CREATE_GROUP');
                    }}
                >
                    {t(groupConstant.createNewGroup.default)}
                </AppButton>
            </Tooltip>
        </div>
    );
}