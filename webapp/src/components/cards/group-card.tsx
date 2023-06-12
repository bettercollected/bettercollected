import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import DeleteIcon from '@Components/Common/Icons/Delete';
import { Typography } from '@mui/material';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { formConstant } from '@app/constants/locales/form';
import { localesGlobal } from '@app/constants/locales/global';
import { members } from '@app/constants/locales/members';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useDeleteResponderGroupMutation } from '@app/store/workspaces/api';

export default function GroupCard({ responderGroup }: { responderGroup: ResponderGroupDto }) {
    const { t } = useTranslation();
    const router = useRouter();
    const { openModal, closeModal } = useModal();
    const [trigger] = useDeleteResponderGroupMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const isAdmin = useAppSelector(selectIsAdmin);
    const handleDeletegroup = async () => {
        try {
            await trigger({
                workspaceId: workspace.id,
                groupId: responderGroup.id
            }).unwrap();
            toast(t(toastMessage.groupDeleted).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            closeModal();
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    const handlePreviewGroup = (event: any) => {
        event.preventDefault();
        router.push(`/${workspace.workspaceName}/dashboard/responders/${responderGroup.id}`);
    };
    return (
        <div onClick={handlePreviewGroup} className="flex cursor-pointer flex-col justify-between border-[2px] border-brand-100 hover:border-black-500 transition shadow-formCard bg-white items-start p-5 rounded-[8px] relative">
            {isAdmin && (
                <DeleteIcon
                    onClick={(event) => {
                        event.stopPropagation();
                        event.preventDefault();
                        openModal('DELETE_CONFIRMATION', { title: responderGroup.name, handleDelete: handleDeletegroup });
                    }}
                    className="absolute text-red-600 top-3 right-3 cursor-pointer h-7 w-7 p-1 rounded hover:bg-black-200"
                />
            )}
            <div>
                <div className="flex gap-2 items-center">
                    <div className="!h-6 !w-6 flex justify-center items-center bg-black-500 rounded">
                        <Typography className="sh1 !leading-none !text-white">{responderGroup.name[0].toUpperCase()}</Typography>
                    </div>
                    <Typography className="body1 !leading-none">{responderGroup.name}</Typography>
                </div>
                {responderGroup.description && <p className="body4 line-clamp-2 break-all !text-black-800 mt-4 !leading-none">{responderGroup.description}</p>}
            </div>

            <p className="my-10 body6 !leading-none">
                {responderGroup.emails.length > 1 ? t(members.default) : t(members.member)} ({responderGroup.emails.length})
            </p>
            <p className="body6 !leading-none">
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
