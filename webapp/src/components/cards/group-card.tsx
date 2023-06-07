import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AddMember from '@Components/Common/Icons/Add-member';
import DeleteIcon from '@Components/Common/Icons/Delete';
import EditIcon from '@Components/Common/Icons/Edit';
import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
import Preview from '@Components/Common/Icons/Preview';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { Button, ListItemIcon, MenuItem, Typography } from '@mui/material';
import { group } from 'console';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { formConstant } from '@app/constants/locales/form';
import { localesGlobal } from '@app/constants/locales/global';
import { groupConstant } from '@app/constants/locales/group';
import { members } from '@app/constants/locales/members';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteResponderGroupMutation, useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';

export default function GroupCard({ responderGroup }: { responderGroup: ResponderGroupDto }) {
    const { openModal } = useModal();
    const { t } = useTranslation();
    const router = useRouter();
    const [trigger] = useDeleteResponderGroupMutation();
    const workspace = useAppSelector((state) => state.workspace);

    const handleDeletegroup = async () => {
        try {
            await trigger({
                workspaceId: workspace.id,
                groupId: responderGroup.id
            }).unwrap();
            toast(t(toastMessage.groupDeleted).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    const handlePreviewGroup = (e: any) => {
        e.preventDefault();
        // return openModal('PREVIEW_GROUP', { responderGroup: responderGroup });
        router.push(`/${workspace.workspaceName}/dashboard/responders/${responderGroup.id}`);
    };
    const handleUpdateGroup = () => {
        return openModal('CREATE_GROUP', { responderGroup: responderGroup });
    };
    const menuItems = [
        {
            icon: Preview,
            text: t(groupConstant.menu.preview),
            onClick: handlePreviewGroup
        },
        {
            icon: EditIcon,
            text: t(groupConstant.menu.edit),
            onClick: handleUpdateGroup
        },
        {
            icon: DeleteIcon,
            text: t(groupConstant.menu.delete),
            onClick: handleDeletegroup
        }
    ];
    return (
        <div onClick={handlePreviewGroup} className="flex cursor-pointer flex-col justify-between border-[2px] border-brand-100 hover:border-black-500 transition shadow-formCard bg-white items-start p-5 rounded-[8px] relative">
            {/* <MenuDropdown showExpandMore={false} className="absolute top-3 right-3 cursor-pointer" width={180} id="group-option" menuTitle={''} menuContent={<EllipsisOption className="rotate-90 " />}>
                {menuItems.map((menuItem) => (
                    <MenuItem key={menuItem.text} disabled={!isAdmin && menuItem.text !== 'Preview'} onClick={menuItem.onClick} className="py-3 hover:bg-black-200">
                        <ListItemIcon>{React.createElement(menuItem.icon, { className: 'h-5 w-5' })}</ListItemIcon>
                        <span className="body4">{menuItem.text}</span>
                    </MenuItem>
                ))}
            </MenuDropdown> */}
            <div>
                <div className="flex gap-2 items-center">
                    <div className="!h-6 !w-6 flex justify-center items-center bg-black-500 rounded">
                        <Typography className="sh1 !text-white">{responderGroup.name[0].toUpperCase()}</Typography>
                    </div>
                    <Typography className="body1">{responderGroup.name}</Typography>
                </div>
                {responderGroup.description && <p className="body4 line-clamp-2 break-all !text-black-800 mt-4">{responderGroup.description}</p>}
            </div>

            <p className="my-10 body6">
                {responderGroup.emails.length > 1 ? t(members.default) : t(members.member)} ({responderGroup.emails.length})
            </p>
            <p className="body6">
                {responderGroup.forms.length > 1 ? t(localesGlobal.forms) : t(formConstant.default)} ({responderGroup.forms.length})
            </p>

            {/* <Button className="!px-3 !py-[9px] !bg-white border !border-black-400  hover:!bg-brand-200" size="medium">
                <div className="flex items-center gap-[5px]">
                    <Send className="h-[20px] w-[20px] text-black-900" />
                    <Typography>Send Form</Typography>
                </div>
            </Button> */}
        </div>
    );
}
