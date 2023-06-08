import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import DeleteIcon from '@Components/Common/Icons/Delete';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { CheckCircle, Groups } from '@mui/icons-material';
import { FormGroup, MenuItem, Typography } from '@mui/material';
import cn from 'classnames';

import EmptyGroup from '@app/components/dashboard/empty-group';
import UserMore from '@app/components/icons/user-more';
import { useModal } from '@app/components/modal-views/context';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import Loader from '@app/components/ui/loader';
import { buttonConstant } from '@app/constants/locales/button';
import { formConstant } from '@app/constants/locales/form';
import { groupConstant } from '@app/constants/locales/group';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllRespondersGroupQuery } from '@app/store/workspaces/api';
import { isFormAlreadyInGroup } from '@app/utils/groupUtils';

export default function FormGroups(props: any) {
    const { t } = useTranslation();
    const form: StandardFormDto = useAppSelector((state) => state.form);
    const { deleteFormFromGroup, addFormOnGroup } = useGroupForm();
    const { openModal } = useModal();
    const { data, isLoading } = useGetAllRespondersGroupQuery(props.workspaceId);
    const isAdmin = useAppSelector(selectIsAdmin);
    const NoGroupLink = () => (
        <div className="mt-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body1">{form.groups?.length === 0 && data?.length === 0 ? t(groupConstant.createAGroupTo) : t(formConstant.addGroup)}</p>
            <ul className="list-disc body4 text-black-700 flex flex-col gap-4 mt-4">
                <li>{t(groupConstant.limitAccessToFrom)}</li>
                <li>{t(groupConstant.sendFormsToMultiplePeople)}</li>
            </ul>
            {AddGroupButton()}
        </div>
    );
    const AddGroupButton = () => (
        <div className={cn('flex justify-center  mt-4', data?.length === 0 && form.groups?.length === 0 && 'cursor-not-allowed opacity-30 pointer-events-none')}>
            <MenuDropdown
                showExpandMore={false}
                className="cursor-pointer "
                width={180}
                id="group-option"
                menuTitle={''}
                menuContent={<div className="bg-brand-500 px-3 rounded text-white py-1">{data?.length === 0 && form.groups?.length === 0 ? t(groupConstant.askAdminToCreateAGroup) : t(buttonConstant.addGroup)}</div>}
            >
                {data.map((group: ResponderGroupDto) => (
                    <MenuItem
                        disabled={isFormAlreadyInGroup(form.groups, group.id)}
                        onClick={() => addFormOnGroup({ groups: form?.groups, group, workspaceId: props.workspaceId, form })}
                        key={group.id}
                        className="py-3 flex justify-between hover:bg-black-200"
                    >
                        <Typography className="body4" noWrap>
                            {group.name}
                        </Typography>
                        {isFormAlreadyInGroup(form.groups, group.id) && <CheckCircle className="h-5 w-5 text-brand-500" />}
                    </MenuItem>
                ))}
            </MenuDropdown>
        </div>
    );

    const ShowFormGroups = () => (
        <div className="flex flex-col gap-4">
            {form.groups?.map((group) => (
                <div key={group.id} className="flex items-center bg-white justify-between p-4">
                    <p>{group.name}</p>

                    <DeleteIcon
                        className="h-7 w-7 text-red-600  cursor-pointer rounded p-1 hover:bg-black-200 "
                        onClick={() => openModal('DELETE_CONFIRMATION', { title: group.name, handleDelete: () => deleteFormFromGroup({ group, workspaceId: props.workspaceId, form }) })}
                    />
                </div>
            ))}
            {AddGroupButton()}
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
            {!isLoading && data?.length === 0 && isAdmin && <EmptyGroup />}
            {!isLoading && data?.length === 0 && !isAdmin && NoGroupLink()}
            {!isLoading && data?.length > 0 && form.groups?.length === 0 && NoGroupLink()}
            {!isLoading && data?.length > 0 && form.groups?.length !== 0 && ShowFormGroups()}
        </FormPageLayout>
    );
}
export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
