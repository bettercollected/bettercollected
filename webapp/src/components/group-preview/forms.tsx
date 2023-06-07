import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import SearchInput from '@Components/Common/Search/SearchInput';
import { CheckCircle } from '@mui/icons-material';
import { MenuItem, Typography } from '@mui/material';

import { Plus } from '@app/components/icons/plus';
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import { buttonConstant } from '@app/constants/locales/button';
import { localesGlobal } from '@app/constants/locales/global';
import { groupConstant } from '@app/constants/locales/group';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';
import { isFormAlreadyInGroup } from '@app/utils/groupUtils';

export default function GroupForms({ group, workspaceForms }: { group: ResponderGroupDto; workspaceForms: Array<StandardFormDto> }) {
    const { t } = useTranslation();
    const workspace = useAppSelector((state) => state.workspace);
    const router = useRouter();
    const { addFormOnGroup } = useGroupForm();
    const handleCardClick = (event: any) => {
        event.preventDefault();
        event.stopPropagation();
        router.push(`/${workspace.workspaceName}/dashboard/forms`);
    };
    const [forms, setForms] = useState(group.forms);
    const handleSearch = (event: any) => {
        const query = event.target.value;
        var updatedList = [...group.forms];
        updatedList = updatedList.filter((item) => {
            return item.title.toLowerCase().indexOf(query.toLowerCase()) !== -1;
        });
        setForms(updatedList);
    };
    return (
        <div>
            <div className="flex  justify-between">
                <p className="body1">
                    {t(localesGlobal.forms)} ({group.forms?.length})
                </p>
                <MenuDropdown
                    showExpandMore={false}
                    className="cursor-pointer "
                    width={180}
                    id="group-option"
                    menuTitle={''}
                    menuContent={
                        <div className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                            <Plus className="h-4 w-4" />
                            <Typography className="!text-brand-500  body6"> {t(buttonConstant.addForm)}</Typography>
                        </div>
                    }
                >
                    {workspaceForms.map((form: StandardFormDto) => (
                        <MenuItem
                            key={form.formId}
                            disabled={isFormAlreadyInGroup(form.groups, group.id)}
                            onClick={() => addFormOnGroup({ group, groups: form.groups, form, workspaceId: workspace.id })}
                            className="py-3 flex justify-between hover:bg-black-200"
                        >
                            <Typography className="body4" noWrap>
                                {form.title}
                            </Typography>
                            {isFormAlreadyInGroup(form.groups, group.id) && <CheckCircle className="h-5 w-5 text-brand-500" />}
                        </MenuItem>
                    ))}
                </MenuDropdown>
            </div>
            <p className="body4 leading-none mt-5 mb-10 md:max-w-[355px] !text-black-700 break-all">{t(groupConstant.description)}</p>
            {group.forms.length > 0 && (
                <div className="gap-6 flex flex-col">
                    <div className="sm:w-[240px]">
                        <SearchInput handleSearch={handleSearch} />
                    </div>
                    <div className="grid mt-6 grid-flow-row md:grid-cols-3 sm:grid-cols-2 grid-cols-1">
                        {forms.map((form, idx) => {
                            return (
                                <div onClick={handleCardClick} key={form.formId + idx}>
                                    <WorkspaceFormCard key={form.formId} form={form} hasCustomDomain={false} workspace={workspace} group={group} />
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
