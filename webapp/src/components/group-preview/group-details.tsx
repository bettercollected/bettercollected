import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Typography } from '@mui/material';

import BetterInput from '@app/components/Common/input';
import { localesGlobal } from '@app/constants/locales/global';
import { groupConstant } from '@app/constants/locales/group';
import { placeHolder } from '@app/constants/locales/placeholder';
import { ResponderGroupDto } from '@app/models/dtos/groups';

export default function GroupDetails({ group }: { group: ResponderGroupDto }) {
    const { t } = useTranslation();
    const [groupInfo, setGroupInfo] = useState({
        name: group.name,
        description: group.description
    });
    const handleInput = (event: any) => {
        setGroupInfo({
            ...groupInfo,
            [event.target.id]: event.target.value
        });
    };
    return (
        <div>
            <div className="h-[120px] mb-4 w-[120px] flex justify-center items-center bg-black-500 rounded-[8px]">
                <Typography className=" text-[90px] font-semibold !text-white">{group.name[0].toUpperCase()}</Typography>
            </div>
            <p className="body4 mt-10 leading-none mb-2">
                {t(groupConstant.name)}
                <span className="text-red-800">*</span>
            </p>
            <BetterInput value={groupInfo.name} className="!mb-0 md:max-w-[618px]" inputProps={{ className: '!py-3' }} id="name" placeholder={t(placeHolder.groupName)} onChange={handleInput} />
            <p className="body4 leading-none mt-6 mb-2">{t(localesGlobal.description)}</p>
            <BetterInput value={groupInfo.description} className="!mb-0 md:max-w-[618px] " inputProps={{ maxLength: 250 }} id="description" placeholder={t(placeHolder.description)} rows={3} multiline onChange={handleInput} />
        </div>
    );
}
