import React from 'react';

import { useTranslation } from 'next-i18next';

import { Typography } from '@mui/material';

import { Plus } from '@app/components/icons/plus';
import { formConstant } from '@app/constants/locales/form';
import { localesGlobal } from '@app/constants/locales/global';
import { groupConstant } from '@app/constants/locales/group';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';

import FormsCard from '../cards/form-card';
import FormCards from '../dashboard/form-cards';
import WorkspaceFormCard from '../workspace-dashboard/workspace-form-card';

export default function GroupForms({ group }: { group: ResponderGroupDto }) {
    const { t } = useTranslation();
    const workspace = useAppSelector((state) => state.workspace);
    return (
        <div>
            <div className="flex  justify-between">
                <p className="body1">
                    {t(localesGlobal.forms)} ({group.forms?.length})
                </p>
                <div className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                    <Plus className="h-4 w-4" />
                    <Typography className="!text-brand-500  body6"> Add Form</Typography>
                </div>
            </div>
            <p className="body4 leading-none mt-5 mb-10 md:max-w-[355px] !text-black-700 break-all">{t(groupConstant.description)}</p>
            <div className="grid mt-6 grid-flow-row md:grid-cols-3 sm:grid-cols-2 grid-cols-1">
                {group.forms.map((form) => {
                    return <WorkspaceFormCard key={form.formId} form={form} hasCustomDomain={false} workspace={workspace} />;
                })}
            </div>
        </div>
    );
}
