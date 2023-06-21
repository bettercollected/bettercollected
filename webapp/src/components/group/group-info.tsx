import React from 'react';

import { useTranslation } from 'next-i18next';

import BetterInput from '@app/components/Common/input';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { placeHolder } from '@app/constants/locales/placeholder';
import { GroupInfoDto } from '@app/models/dtos/groups';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

interface IGroupInfoProps {
    handleInput: (e: any) => void;
    groupInfo: GroupInfoDto;
}

export default function GroupInfo({ handleInput, groupInfo }: IGroupInfoProps) {
    const { t } = useTranslation();
    const isAdmin = useAppSelector(selectIsAdmin);
    return (
        <div>
            <p className="body1">{t(groupConstant.basicInformation)}</p>
            <p className="body4 mt-4 leading-none mb-2">
                {t(groupConstant.name)}
                <span className="text-red-800">*</span>
            </p>
            <BetterInput disabled={!isAdmin} value={groupInfo.name} className="!mb-0 bg-white " inputProps={{ className: '!py-3' }} id="name" placeholder={t(placeHolder.groupName)} onChange={handleInput} />
            <p className="body4 leading-none mt-6 mb-2">{t(localesCommon.description)}</p>
            <BetterInput disabled={!isAdmin} value={groupInfo.description} className="!mb-0 bg-white " inputProps={{ maxLength: 250 }} id="description" placeholder={t(placeHolder.description)} rows={3} multiline onChange={handleInput} />
        </div>
    );
}
