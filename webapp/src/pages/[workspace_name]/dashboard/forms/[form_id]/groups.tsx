import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import DeleteIcon from '@Components/Common/Icons/Delete';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { CheckCircle, Groups } from '@mui/icons-material';
import { FormGroup, MenuItem, Typography } from '@mui/material';
import { toast } from 'react-toastify';

import GroupCard from '@app/components/cards/group-card';
import EmptyGroup from '@app/components/dashboard/empty-group';
import { Check } from '@app/components/icons/check';
import UserMore from '@app/components/icons/user-more';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import Button from '@app/components/ui/button';
import Loader from '@app/components/ui/loader';
import { buttonConstant } from '@app/constants/locales/buttons';
import { formConstant } from '@app/constants/locales/form';
import { groupConstant } from '@app/constants/locales/group';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useAddFormOnGroupMutation, useDeleteGroupFormMutation, useGetAllRespondersGroupQuery, useGetSingleFormFromProviderQuery } from '@app/store/workspaces/api';
import { isFormAlreadyInGroup } from '@app/utils/groupUtils';

export default function FormGroups(props: any) {
    const { t } = useTranslation();
    const form: StandardFormDto = useAppSelector((state) => state.form);
    const dispatch = useAppDispatch();
    const { data, isLoading } = useGetAllRespondersGroupQuery(props.workspaceId);
    const [addGroup] = useAddFormOnGroupMutation();
    const [removeGroup] = useDeleteGroupFormMutation();
    const deleteFormFromGroup = async (group: ResponderGroupDto) => {
        try {
            await removeGroup({
                workspaceId: props.workspaceId,
                groupId: group.id,
                formId: form.formId
            }).unwrap();

            dispatch(setForm({ ...form, groups: form.groups?.filter((formGroup) => formGroup.id !== group.id) }));

            toast(t(toastMessage.removeFromGroup).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };

    const addFormOnGroup = async (groups: any, group: ResponderGroupDto) => {
        try {
            await addGroup({
                workspaceId: props.workspaceId,
                groupId: group.id,
                formId: form.formId
            }).unwrap();

            dispatch(setForm({ ...form, groups: [...groups, group] }));

            toast(t(toastMessage.addedOnGroup).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    const NoGroupLink = () => (
        <div className="mt-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body1">{t(formConstant.addGroup)}</p>
            <ul className="list-disc body4 text-black-700 flex flex-col gap-4 mt-4">
                <li>{t(groupConstant.limitAccessToFrom)}</li>
                <li>{t(groupConstant.sendFormsToMultiplePeople)}</li>
            </ul>
        </div>
    );

    const ShowFormGroups = () => (
        <div className="flex flex-col gap-4">
            {form.groups?.map((group) => (
                <div key={group.id} className="flex items-center bg-white justify-between p-4">
                    <p>{group?.name}</p>
                    <DeleteIcon className="h-6 w-6 text-red-600  cursor-pointer" onClick={() => deleteFormFromGroup(group)} />
                </div>
            ))}
            <div className="flex justify-center mt-4">
                <MenuDropdown showExpandMore={false} className="cursor-pointer " width={180} id="group-option" menuTitle={''} menuContent={<div className="bg-brand-500 px-3 rounded text-white py-1">{t(buttonConstant.addGroup)}</div>}>
                    {data.map((group: ResponderGroupDto) => (
                        <MenuItem disabled={isFormAlreadyInGroup(form.groups, group.id)} onClick={() => addFormOnGroup(form?.groups, group)} key={group.id} className="py-3 flex justify-between hover:bg-black-200">
                            <Typography className="body4" noWrap>
                                {group.name}
                            </Typography>
                            {isFormAlreadyInGroup(form.groups, group.id) && <CheckCircle className="h-5 w-5 text-brand-500" />}
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
