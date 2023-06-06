import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import DeleteIcon from '@Components/Common/Icons/Delete';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { MenuItem } from '@mui/material';
import { toast } from 'react-toastify';

import GroupCard from '@app/components/cards/group-card';
import EmptyGroup from '@app/components/dashboard/empty-group';
import UserMore from '@app/components/icons/user-more';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import Button from '@app/components/ui/button';
import Loader from '@app/components/ui/loader';
import { formConstant } from '@app/constants/locales/form';
import { groupConstant } from '@app/constants/locales/group';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useAddFormOnGroupMutation, useDeleteGroupFormMutation, useGetAllRespondersGroupQuery, useGetRespondersGroupQuery, useGetSingleFormFromProviderQuery } from '@app/store/workspaces/api';

export default function FormGroups(props: any) {
    const { t } = useTranslation();
    const form = useAppSelector((state) => state.form);
    const dispatch = useAppDispatch();
    const { data, isLoading } = useGetAllRespondersGroupQuery(props.workspaceId);
    const [addGroup] = useAddFormOnGroupMutation();
    const [removeGroup] = useDeleteGroupFormMutation();
    const deleteFormFromGroup = async (groupId: string) => {
        try {
            await removeGroup({
                workspaceId: props.workspaceId,
                groupId: groupId,
                formId: form.formId
            }).unwrap();
            dispatch(setForm({ ...form, groups: form.groups.filter((group) => group !== groupId) }));

            toast(t(toastMessage.removeFromGroup).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };

    const addFormOnGroup = async (groups: Array<string>, groupId: string) => {
        try {
            if (groups.includes(groupId)) {
                toast(t(toastMessage.alreadyInGroup).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
                return;
            }

            await addGroup({
                workspaceId: props.workspaceId,
                groupId: groupId,
                formId: form.formId
            }).unwrap();

            dispatch(setForm({ ...form, groups: [...groups, groupId] }));

            toast(t(toastMessage.addedOnGroup).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    const NoGroupLink = () => (
        <div className="mt-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body1">Add form on group</p>
            <ul className="list-disc body4 text-black-700 flex flex-col gap-4 mt-4">
                <li>{t(groupConstant.limitAccessToFrom)}</li>
                <li>{t(groupConstant.sendFormsToMultiplePeople)}</li>
            </ul>
        </div>
    );

    const ShowFormGroups = () => (
        <div className="flex flex-col gap-4">
            {form.groups.map((group) => (
                <div key={group} className="flex items-center bg-white justify-between p-4">
                    <p>{group}</p>
                    <DeleteIcon className="h-6 w-6 text-red-600  cursor-pointer" onClick={() => deleteFormFromGroup(group)} />
                </div>
            ))}
            <div className="flex justify-center mt-4">
                <MenuDropdown showExpandMore={false} className="cursor-pointer " width={180} id="group-option" menuTitle={''} menuContent={<div className="bg-brand-500 px-3 rounded text-white py-1">Add More Group</div>}>
                    {data.map((group: ResponderGroupDto) => (
                        <MenuItem onClick={() => addFormOnGroup(form.groups, group.id)} key={group.id} className="py-3 hover:bg-black-200">
                            <span className="body4">{group.name}</span>
                        </MenuItem>
                    ))}
                </MenuDropdown>
            </div>
        </div>
    );
    return (
        <FormPageLayout {...props}>
            {isLoading && (
                <div className=" w-full py-10 flex justify-center">
                    <Loader />
                </div>
            )}
            {!isLoading && (
                <div>
                    <div className="heading4">{t(groupConstant.groups)}</div>
                    <Divider className="my-4" />
                </div>
            )}
            {!isLoading && data?.length === 0 && EmptyGroup()}
            {!isLoading && form.groups?.length === 0 && NoGroupLink()}
            {!isLoading && data?.length > 0 && ShowFormGroups()}
        </FormPageLayout>
    );
}
export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
