import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { Typography } from '@mui/material';
import { toast } from 'react-toastify';

import GroupCard from '@app/components/cards/group-card';
import EmptyGroup from '@app/components/dashboard/empty-group';
import { Plus } from '@app/components/icons/plus';
import { useModal } from '@app/components/modal-views/context';
import Loader from '@app/components/ui/loader';
import { groupConstant } from '@app/constants/locales/group';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteResponderGroupMutation, useGetAllRespondersGroupQuery } from '@app/store/workspaces/api';

export default function WorkspaceGroups({ workspace }: { workspace: WorkspaceDto }) {
    const { openModal, closeModal } = useModal();
    const { t } = useTranslation();
    const isAdmin = useAppSelector(selectIsAdmin);
    const { data, isLoading } = useGetAllRespondersGroupQuery(workspace.id);
    const [trigger] = useDeleteResponderGroupMutation();
    const router = useRouter();
    const handleDeletegroup = async (group: ResponderGroupDto) => {
        try {
            await trigger({
                workspaceId: workspace.id,
                groupId: group.id
            });
            toast(t(toastMessage.groupDeleted).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            closeModal();
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    const Group = () => (
        <div>
            <div className="flex justify-between">
                <div className="flex  gap-[72px] mb-8 items-center ">
                    <div className="flex flex-col">
                        <div className="flex justify-between flex-col xs:flex-row">
                            <p className="body1">
                                {t(groupConstant.groups)} {data && ' (' + data.length + ')'}{' '}
                            </p>
                            {isAdmin && (
                                <AppButton variant={ButtonVariant.Ghost} className="w-fit" icon={<Plus className="h-4 w-4" />} onClick={() => router.push(`/${workspace?.workspaceName}/dashboard/responders-groups/create-group`)}>
                                    <Typography className="!text-brand-500  body6"> {t(groupConstant.createGroup)}</Typography>
                                </AppButton>
                            )}
                        </div>
                        <p className="mt-2  body4 text-black-700">{t(groupConstant.description)}</p>
                    </div>
                </div>
            </div>

            <div className="grid sm:grid-cols-2 2xl:grid-cols-3  grid-flow-row gap-6">
                {data &&
                    data?.map((group: ResponderGroupDto) => {
                        return <GroupCard key={group.id} responderGroup={group} handleDelete={() => handleDeletegroup(group)} />;
                    })}
            </div>
        </div>
    );
    if (isLoading)
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    if (data && data?.length > 0) return Group();
    return <EmptyGroup />;
}
