"use client";

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/navigation';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import DataTable from 'react-data-table-component';

import { dataTableCustomStyles } from '@app/Components/datatable/form/datatable-styles';
import { Plus } from '@app/Components/icons/plus';
import { useModal } from '@app/Components/modal-views/context';
import DeleteDropDown from '@app/Components/ui/delete-dropdown';
import Loader from '@app/Components/ui/loader';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteResponderGroupMutation, useGetAllRespondersGroupQuery } from '@app/store/workspaces/api';
import EmptyGroup from '@Components/dashboard/empty-group';

const customGroupTableStyles: any = { ...dataTableCustomStyles };

customGroupTableStyles.rows.style.cursor = 'pointer';
export default function WorkspaceGroups({ workspace }: { workspace: WorkspaceDto }) {
    const { toast } = useToast();
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
            toast({ description: t(toastMessage.groupDeleted).toString() });
            closeModal();
        } catch (error) {
            toast({ description: t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
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
                        <Button
                            variant="ghost"
                            className="w-fit"
                            icon={<Plus className="h-4 w-4" />}
                            onClick={() => {
                                openBottomSheetModal('CREATE_GROUP');
                            }}
                        >
                            <span className="!text-brand-500  body6"> {t(groupConstant.createGroup)}</span>
                        </Button>
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
