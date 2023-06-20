import React from 'react';

import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';

import UserMore from '@app/components/icons/user-more';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { groupConstant } from '@app/constants/locales/group';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

export default function EmptyGroup() {
    const { t } = useTranslation();
    const { openModal } = useModal();
    const isAdmin = useAppSelector(selectIsAdmin);
    return (
        <div className="my-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body2 text-center !font-medium sm:w-[252px] mt-7 mb-6">{t(groupConstant.title)}</p>
            <Tooltip title={!isAdmin ? t(toolTipConstant.noAccessToGroup) : ''}>
                <Button disabled={!isAdmin} size="small" onClick={() => openModal('CREATE_GROUP')}>
                    {t(groupConstant.createNewGroup.default)}
                </Button>
            </Tooltip>
        </div>
    );
}
