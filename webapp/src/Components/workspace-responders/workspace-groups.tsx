import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import { Typography } from '@mui/material';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';

import EmptyGroup from '@Components/dashboard/empty-group';
import { dataTableCustomStyles } from '@app/Components/datatable/form/datatable-styles';
import { Plus } from '@app/Components/icons/plus';
import { useModal } from '@app/Components/modal-views/context';
import DeleteDropDown from '@app/Components/ui/delete-dropdown';
import Loader from '@app/Components/ui/loader';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteResponderGroupMutation, useGetAllRespondersGroupQuery } from '@app/store/workspaces/api';

const customGroupTableStyles: any = { ...dataTableCustomStyles };

customGroupTableStyles.rows.style.cursor = 'pointer';
export default function WorkspaceGroups({ workspace }: { workspace: WorkspaceDto }) {
    const { openModal, closeModal } = useModal();
    const { t } = useTranslation();

    const router = useRouter();

    const isAdmin = useAppSelector(selectIsAdmin);
    const { data, isLoading } = useGetAllRespondersGroupQuery(workspace.id);
    const [trigger] = useDeleteResponderGroupMutation();

    const { openBottomSheetModal } = useBottomSheetModal();

    const handleDeleteGroup = async (group: ResponderGroupDto) => {
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

    const onGroupClicked = (group: ResponderGroupDto) => {
        router.push(`/${workspace.workspaceName}/dashboard/responders-groups/${group.id}`);
    };

    const columns: any = [
        {
            name: t('GROUP.DEFAULT'),
            selector: (group: ResponderGroupDto) => group.name,
            style: {
                color: '#202124',
                fontSize: '14px',
                fontWeight: 500,
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: t('GROUP.MEMBERS.DEFAULT'),
            selector: (group: ResponderGroupDto) => group.emails?.length ?? 0,
            style: {
                color: '#202124',
                fontSize: '14px',
                fontWeight: 500,
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: t('FORMS'),
            selector: (group: ResponderGroupDto) => group.forms.length,
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
            width: '60px',
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
                <div className="mb-8 flex w-full items-center justify-between ">
                    <div className="flex flex-col">
                        <div className="xs:flex-row flex flex-col justify-between">
                            <p className="h3-new font-semibold">
                                {t(groupConstant.groups)} {data && ' (' + data.length + ')'}{' '}
                            </p>
                        </div>
                        <p className="body4 text-black-700 mt-2">{t(groupConstant.description)}</p>
                    </div>
                    {isAdmin && (
                        <AppButton
                            variant={ButtonVariant.Ghost}
                            className="w-fit"
                            icon={<Plus className="h-4 w-4" />}
                            onClick={() => {
                                openBottomSheetModal('CREATE_GROUP');
                            }}
                        >
                            <Typography className="!text-brand-500  body6"> {t(groupConstant.createGroup)}</Typography>
                        </AppButton>
                    )}
                </div>
            </div>

            <div className=" w-full">
                {data && (
                    <DataTable
                        onRowClicked={(group: ResponderGroupDto) => {
                            onGroupClicked(group);
                        }}
                        columns={columns}
                        data={data}
                        customStyles={customGroupTableStyles}
                    />
                )}
            </div>
        </div>
    );
    if (isLoading)
        return (
            <div className=" flex w-full justify-center py-10">
                <Loader />
            </div>
        );
    if (data && data?.length > 0) return Group();
    return <EmptyGroup />;
}
