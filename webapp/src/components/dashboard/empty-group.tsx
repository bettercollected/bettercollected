import React from 'react';

import { useTranslation } from 'next-i18next';

import UserMore from '@app/components/icons/user-more';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { groupConstant } from '@app/constants/locales/group';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

export default function EmptyGroup() {
    const { t } = useTranslation();
    const { openModal } = useModal();
    const isAdmin = useAppSelector(selectIsAdmin);
    return (
        <div className="my-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body1">{t(groupConstant.createAGroupTo)} :</p>
            <ul className="list-disc body4 text-black-700 flex flex-col gap-4 mt-4">
                <li>{t(groupConstant.limitAccessToFrom)}</li>
                <li>{t(groupConstant.sendFormsToMultiplePeople)}</li>
            </ul>
            <Button disabled={!isAdmin} className="mt-6" size="small" onClick={() => openModal('CREATE_GROUP')}>
                {t(groupConstant.createNewGroup.default)}
            </Button>
        </div>
    );
}
