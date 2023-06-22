import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import SearchInput from '@Components/Common/Search/SearchInput';
import { CheckCircle } from '@mui/icons-material';
import { MenuItem, Typography } from '@mui/material';

import { Plus } from '@app/components/icons/plus';
import WorkspaceFormCard from '@app/components/workspace-dashboard/workspace-form-card';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { isFormAlreadyInGroup } from '@app/utils/groupUtils';

import { useModal } from '../modal-views/context';

export default function GroupFormsTab({ group, workspaceForms }: { group: ResponderGroupDto; workspaceForms: Array<StandardFormDto> }) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const isAdmin = useAppSelector(selectIsAdmin);

    const { addFormOnGroup } = useGroupForm();
    const handleCardClick = (event: any) => {
        event.preventDefault();
        event.stopPropagation();
        router.push(`/${workspace.workspaceName}/dashboard/forms`);
    };
    const [forms, setForms] = useState(group.forms);
    const [searchQuery, setSearchQuery] = useState('');
    const { openModal } = useModal();
    useEffect(() => {
        setForms(group.forms);
    }, [group]);

    const handleSearch = (event: any) => {
        const query = event.target.value.toLowerCase();
        setSearchQuery(query);
    };

    useEffect(() => {
        const filteredForms = group.forms.filter((form) => {
            return form.title.toLowerCase().includes(searchQuery);
        });
        setForms(filteredForms);
    }, [searchQuery, group]);

    return (
        <div>
            <div className="flex items-center  mb-10 md:max-w-[618px]  justify-between">
                <div className="flex flex-col gap-4">
                    <p className="body1 !leading-none">
                        {t(localesCommon.forms)} ({group.forms?.length})
                    </p>
                    <p className="body4 leading-none   !text-black-700 ">{t(groupConstant.form.description)}</p>
                </div>
                {isAdmin && (
                    <Tooltip title={workspaceForms.length === 0 ? t(toolTipConstant.emptyFormOnWorkspace) : ''}>
                        <button disabled={workspaceForms.length === 0} onClick={() => openModal('ADD_FORM_GROUP', { forms: workspaceForms, group })} className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                            <Plus className="h-4 w-4" />
                            <Typography className="!text-brand-500 min-w-[65px]  body6"> {t(buttonConstant.addForm)}</Typography>
                        </button>
                    </Tooltip>
                )}
            </div>
            {group.forms.length > 0 && (
                <div className="gap-6 flex flex-col">
                    <div className="sm:w-[240px]">
                        <SearchInput handleSearch={handleSearch} />
                    </div>
                    <div className="grid mt-6 grid-flow-row xl:grid-cols-4 md:grid-cols-3 sm:grid-cols-2 grid-cols-1 gap-6">
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
