import React from 'react';

import { useTranslation } from 'next-i18next';

import Plus from '@Components/Common/Icons/Common/Plus';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';

import GroupCard from '@Components/cards/group-card';
import EmptyGroup from '@Components/dashboard/empty-group';
import { useModal } from '@app/Components/modal-views/context';
import Loader from '@app/Components/ui/loader';
import { buttonConstant } from '@app/constants/locales/button';
import { formConstant } from '@app/constants/locales/form';
import { groupConstant } from '@app/constants/locales/group';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllRespondersGroupQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';


export default function FormGroups() {
    const { t } = useTranslation();
    const form: StandardFormDto = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openModal } = useModal();
    const { deleteFormFromGroup } = useGroupForm();
    const { data, isLoading } = useGetAllRespondersGroupQuery(workspace.id);

    const ShowFormGroups = () => (
        <div className="flex flex-col gap-4">
            <p className="body1">
                {t(groupConstant.groups)} ({form.groups?.length || 0})
            </p>
            <div className="flex  gap-[72px] items-center ">
                <p className="body4 !text-black-700 md:w-[450px] ">{t(formConstant.group.description)}</p>
                <AppButton icon={<Plus className="h-4 w-4" />} onClick={() => openModal('ADD_GROUP_FORM', { responderGroups: data, form })} variant={ButtonVariant.Ghost}>
                    {t(buttonConstant.addGroup)}
                </AppButton>
            </div>
            <div className="grid grid-flow-row md:grid-cols-2 mt-6 xl:grid-cols-3 grid-cols-1 gap-6">
                {form.groups?.map((group: ResponderGroupDto) => (
                    <GroupCard key={group.id} responderGroup={group} isFormGroup={true} handleDelete={() => deleteFormFromGroup({ group, workspaceId: workspace.id, form })} />
                ))}
            </div>
        </div>
    );
    if (isLoading)
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    else if (data && data?.length === 0) return <EmptyGroup formId={form.formId} />;
    else return ShowFormGroups();
}