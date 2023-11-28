import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { Typography } from '@mui/material';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';

import GroupCard from '@app/components/cards/group-card';
import EmptyGroup from '@app/components/dashboard/empty-group';
import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import { Plus } from '@app/components/icons/plus';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import DeleteDropDown from '@app/components/ui/delete-dropdown';
import Loader from '@app/components/ui/loader';
import { localesCommon } from '@app/constants/locales/common';
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

    const fullScreenModal = useFullScreenModal();

    const handleDeleteGroup = async (group: ResponderGroupDto) => {
        try {
            console.log(group);
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

    const columns: any = [
        {
            name: 'Group',
            selector: (group: ResponderGroupDto) => group.name,
            grow: 2,
            style: {
                color: '#202124',
                fontSize: '14px',
                fontWeight: 500,
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: 'Members',
            selector: (group: ResponderGroupDto) => group.emails?.length ?? 0,
            grow: 2,
            style: {
                color: '#202124',
                fontSize: '14px',
                fontWeight: 500,
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: 'Forms',
            selector: (group: ResponderGroupDto) => group.forms.length,
            grow: 2,
            style: {
                color: '#202124',
                fontSize: '14px',
                fontWeight: 500,
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: '',
            style: {
                justifyContent: 'end',
                display: 'flex',
                paddingRight: 16
            },
            selector: (group: ResponderGroupDto) => (
                <div className="flex w-full justify-end">
                    <DeleteDropDown
                        onDropDownItemClick={(event) => {
                            event.stopPropagation();
                            event.preventDefault();
                            openModal('DELETE_CONFIRMATION', {
                                title: t(localesCommon.delete) + ' ' + group.name,
                                handleDelete: () => {
                                    handleDeleteGroup(group);
                                }
                            });
                        }}
                        label={t(localesCommon.delete)}
                    />
                </div>
            )
        }
    ];

    const Group = () => (
        <div>
            <div className="flex justify-between">
                <div className="flex justify-between w-full mb-8 items-center ">
                    <div className="flex flex-col">
                        <div className="flex justify-between flex-col xs:flex-row">
                            <p className="h3-new font-semibold">
                                {t(groupConstant.groups)} {data && ' (' + data.length + ')'}{' '}
                            </p>
                        </div>
                        <p className="mt-2 body4 text-black-700">{t(groupConstant.description)}</p>
                    </div>
                    {isAdmin && (
                        <AppButton
                            variant={ButtonVariant.Ghost}
                            className="w-fit"
                            icon={<Plus className="h-4 w-4" />}
                            onClick={() => {
                                fullScreenModal.openModal('CREATE_GROUP');
                            }}
                        >
                            <Typography className="!text-brand-500  body6"> {t(groupConstant.createGroup)}</Typography>
                        </AppButton>
                    )}
                </div>
            </div>

            <div className=" w-full">{data && <DataTable columns={columns} data={data} customStyles={dataTableCustomStyles} />}</div>
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
