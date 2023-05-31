import React from 'react';

import { useTranslation } from 'next-i18next';

import AddMember from '@Components/Common/Icons/Add-member';
import DeleteIcon from '@Components/Common/Icons/Delete';
import EditIcon from '@Components/Common/Icons/Edit';
import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
import Preview from '@Components/Common/Icons/Preview';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { ListItemIcon, MenuItem, Typography } from '@mui/material';
import { toast } from 'react-toastify';

import { buttonConstant } from '@app/constants/locales/buttons';
import { formConstant } from '@app/constants/locales/form';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteResponderGroupMutation } from '@app/store/workspaces/api';

import { Telegram } from '../icons/brands/telegram';
import { useModal } from '../modal-views/context';
import Button from '../ui/button/button';

export default function GroupCard({ responderGroup }: { responderGroup: ResponderGroupDto }) {
    const { openModal } = useModal();
    const { t } = useTranslation();
    const [trigger] = useDeleteResponderGroupMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const handleDeletegroup = async () => {
        const response: any = await trigger({
            workspaceId: workspace.id,
            groupId: responderGroup.id
        });
        if (response?.data) {
            toast(response.data, { toastId: ToastId.SUCCESS_TOAST });
        } else {
            toast(response?.error || t(toastMessage.somethingWentWrong), { toastId: ToastId.ERROR_TOAST });
        }
    };
    return (
        <div className="flex flex-col justify-between bg-white items-start p-5 rounded-[8px] relative">
            <MenuDropdown
                showExpandMore={false}
                className="absolute top-5 right-5 cursor-pointer"
                width={180}
                id="group-option"
                menuTitle={''}
                menuContent={
                    <>
                        <EllipsisOption className="rotate-90 " />
                    </>
                }
            >
                <MenuItem onClick={() => openModal('CREATE_GROUP', { responderGroup: responderGroup })} className="py-3 hover:bg-black-200">
                    <ListItemIcon>
                        <Preview width={20} height={20} />
                    </ListItemIcon>
                    Preview
                </MenuItem>
                <MenuItem onClick={() => openModal('CREATE_GROUP', { responderGroup: responderGroup })} className="py-3 hover:bg-black-200">
                    <ListItemIcon>
                        <AddMember width={20} height={20} />
                    </ListItemIcon>
                    Add Member
                </MenuItem>
                <MenuItem onClick={() => openModal('CREATE_GROUP', { responderGroup: responderGroup })} className="py-3 hover:bg-black-200">
                    <ListItemIcon>
                        <EditIcon width={20} height={20} />
                    </ListItemIcon>
                    Edit Group
                </MenuItem>
                <MenuItem onClick={handleDeletegroup} className="py-3 hover:bg-black-200">
                    <ListItemIcon className="!text-red-500">
                        <DeleteIcon width={20} height={20} />
                    </ListItemIcon>
                    <span>Delete Group</span>
                </MenuItem>
            </MenuDropdown>
            <div>
                <div className="flex gap-2 items-center">
                    <div className="!h-6 !w-6 flex justify-center items-center bg-black-500 rounded">
                        <Typography className="sh1 !text-white">{responderGroup.name[0].toUpperCase()}</Typography>
                    </div>
                    <Typography className="body1">{responderGroup.name}</Typography>
                </div>
                {responderGroup.description && <p className="body4 line-clamp-2 break-all text-black-800 mt-4">{responderGroup.description}</p>}
            </div>
            <div>
                <p className="mt-10">Members ({responderGroup.emails.length})</p>
                <div className=" gap-1 line-clamp-2 mt-4 mb-10">
                    {responderGroup.emails.map((email) => {
                        return (
                            <p key={email.identifier} className=" inline-block text-black-800">
                                {email.identifier},
                            </p>
                        );
                    })}
                </div>
            </div>
            <Button className="!px-3 !py-[9px] !bg-white border !border-black-400  hover:!bg-brand-200" size="medium">
                <div className="flex items-center gap-[5px]">
                    <Telegram className="h-[20px] w-[20px] text-black-900" />
                    <Typography>Send Form</Typography>
                </div>
            </Button>
        </div>
    );
}
