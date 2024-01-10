import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import CheckBox from '@Components/Common/Input/CheckBox';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';

import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import { GroupIcon } from '@app/components/icons/group-icon';
import SaveIcon from '@app/components/icons/save';
import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGetAllRespondersGroupQuery, usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

const SelectGroup = () => {
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const { data, isLoading } = useGetAllRespondersGroupQuery(workspace.id);
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const { openModal, closeModal } = useModal();

    const { openBottomSheetModal } = useBottomSheetModal();
    const { addFormOnGroup } = useGroupForm();
    const [selectedGroup, setSelectedGroup] = useState<Array<ResponderGroupDto>>(form?.groups);
    const patchSettings = async (body: any, f: StandardFormDto) => {
        const response: any = await patchFormSettings({
            workspaceId: workspace.id,
            formId: f.formId,
            body: body
        });
        if (response.data) {
            const settings = response.data.settings;
            dispatch(setForm({ ...form, settings }));
        } else {
            if (response.error.status === 409) {
                toast(t('TOAST.SLUG_ALREADY_EXISTS').toString(), { type: 'error' });
            } else {
                toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error' });
            }
            return response.error;
        }
    };
    const handleOnClickCheckbox = (row: ResponderGroupDto, e: any) => {
        if (e.target.checked) {
            setSelectedGroup([...selectedGroup, row]);
        } else {
            setSelectedGroup(selectedGroup.filter((uncheckedRow) => row.id != uncheckedRow.id));
        }
    };
    const handleOnSave = () => {
        if (selectedGroup.length !== 0) {
            addFormOnGroup({
                groups: [],
                groupsForUpdate: selectedGroup,
                form,
                workspaceId: workspace.id
            });
            patchSettings({ hidden: false, private: true, pinned: false }, form);
        } else {
            openModal('VISIBILITY_CONFIRMATION_MODAL_VIEW', {
                visibilityType: 'Group',
                handleOnConfirm: () => {
                    addFormOnGroup({
                        groups: [],
                        groupsForUpdate: selectedGroup,
                        form,
                        workspaceId: workspace.id
                    });
                    closeModal();
                }
            });
        }
    };

    const checkIfRowExistsInGroups = (row: ResponderGroupDto) => {
        let group = selectedGroup.find((data) => data.id === row.id);
        return !!group;
    };

    const MembersColumn = (row: ResponderGroupDto) => {
        if (row.regex) {
            return (
                <div className={'flex flex-row text-sm font-normal text-black-700'}>
                    <GroupIcon className={'mr-2'} /> {row?.emails?.length} members + <span className={'text-pink-500 pl-2'}>{row.regex}</span>
                </div>
            );
        } else {
            return (
                <div className={'flex flex-row text-sm font-normal text-black-700'}>
                    <GroupIcon className={'mr-2'} /> {row?.emails?.length} members
                </div>
            );
        }
    };

    const GroupsColumn = (row: ResponderGroupDto) => {
        return (
            <div>
                <h1 className={'text-base font-semibold text-black-800'}>{row.name}</h1>
                <p className={'text-sm font-normal text-black-700'}>{row.description}</p>
            </div>
        );
    };

    const groupColumns: any = [
        {
            name: '',
            selector: (row: any) => {
                return <CheckBox checked={checkIfRowExistsInGroups(row)} value={row} onClick={(e) => handleOnClickCheckbox(row, e)} />;
            },
            grow: 1,
            minWidth: '40px',
            paddingRight: '0px',
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                fontSize: '16px'
            }
        },
        {
            name: ' Group Name',
            selector: (row: any) => GroupsColumn(row),
            grow: 30,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        },
        {
            name: 'Members',
            selector: (row: any) => MembersColumn(row),
            grow: 30,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px',
                fontSize: '16px'
            }
        }
    ];

    // @ts-ignore
    return (
        <div className={'flex flex-col gap-12 w-full'}>
            <div className={'flex flex-row justify-between'}>
                <div className={'flex flex-col md:w-[660px] gap-3'}>
                    <h1 className={'h2-new !text-black-800'}>Select Group</h1>
                    <p className={'text-sm font-normal text-black-700'}>Only members of the specific groups be able to see the form. You can also create groups with whom you want to share this form.</p>
                </div>
                <AppButton variant={ButtonVariant.Secondary} onClick={() => openBottomSheetModal('CREATE_GROUP')} icon={<GroupIcon className={'text-white'} />} size={ButtonSize.Medium}>
                    Create New Group
                </AppButton>
            </div>
            <DataTable className="p-0 mt-2 h-full !overflow-auto" columns={groupColumns} data={data || []} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
            <div className={'flex flex-row'}>
                <AppButton className="" onClick={handleOnSave} icon={<SaveIcon className={'text-white'} />} size={ButtonSize.Medium}>
                    Save Changes
                </AppButton>
            </div>
        </div>
    );
};

export default SelectGroup;
