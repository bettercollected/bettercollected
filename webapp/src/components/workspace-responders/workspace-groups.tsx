import React from 'react';

import { useTranslation } from 'next-i18next';

import { Typography } from '@mui/material';

import GroupCard from '@app/components/cards/group-card';
import { Plus } from '@app/components/icons/plus';
import UserMore from '@app/components/icons/user-more';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button/button';
import Loader from '@app/components/ui/loader';
import { groupConstant } from '@app/constants/locales/group';
import { ResponderGroupDto } from '@app/models/dtos/groups';

export default function WorkspaceGropus({ responderGroups }: { responderGroups: Array<ResponderGroupDto> }) {
    const { openModal } = useModal();
    const { t } = useTranslation();
    const data = responderGroups;
    const emptyGroup = () => (
        <div className="my-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body1">{t(groupConstant.createAGroupTo)} :</p>
            <ul className="list-disc body4 text-black-700 flex flex-col gap-4 mt-4">
                <li>{t(groupConstant.limitAccessToFrom)}</li>
                <li>{t(groupConstant.sendFormsToMultiplePeople)}</li>
            </ul>
            <Button className="mt-6" size="small" onClick={() => openModal('CREATE_GROUP')}>
                {t(groupConstant.createNewGroup.default)}
            </Button>
        </div>
    );
    const group = () => (
        <div>
            <div className="flex justify-between">
                <p className="body1">
                    {t(groupConstant.groups)} {data && ' (' + data.length + ')'}{' '}
                </p>
                <div onClick={() => openModal('CREATE_GROUP')} className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                    <Plus className="h-4 w-4" />
                    <Typography className="!text-brand-500  body6"> {t(groupConstant.createGroup)}</Typography>
                </div>
            </div>
            <p className="mt-4 mb-8 body4 sm:max-w-[355px] text-black-700">{t(groupConstant.description)}</p>
            <div className="grid sm:grid-cols-2  grid-flow-row gap-6">
                {data &&
                    data?.map((group: ResponderGroupDto) => {
                        return <GroupCard key={group.id} responderGroup={group} />;
                    })}
            </div>
        </div>
    );

    if (data && data?.length > 0) return group();
    return emptyGroup();
}
