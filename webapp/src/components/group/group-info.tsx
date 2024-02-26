import React from 'react';

import { useTranslation } from 'next-i18next';

import AppTextField from '@Components/Common/Input/AppTextField';

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
            {/*<p className="body1">{t(groupConstant.basicInformation)}</p>*/}
            <p className="h4-new !font-medium leading-none mb-2">
                {t(groupConstant.name)}
                <span className="text-red-800">*</span>
            </p>
            <AppTextField disabled={!isAdmin} value={groupInfo.name} id="name" placeholder={t(placeHolder.groupName)} onChange={handleInput} />
            <p className="h4-new leading-none mt-8 !font-medium mb-2">{t(localesCommon.description)}</p>
            <AppTextField disabled={!isAdmin} value={groupInfo.description} id="description" placeholder={t(placeHolder.description)} multiline rows={5} onChange={handleInput} />
        </div>
    );
}