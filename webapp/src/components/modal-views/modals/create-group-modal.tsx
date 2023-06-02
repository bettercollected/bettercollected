import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Close } from '@mui/icons-material';
import cn from 'classnames';
import { useSelector } from 'react-redux';
import { toast } from 'react-toastify';
import { PersistPartial } from 'redux-persist/es/persistReducer';

import BetterInput from '@app/components/Common/input';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button/button';
import { buttonConstant } from '@app/constants/locales/buttons';
import { localesGlobal } from '@app/constants/locales/global';
import { groupConstant } from '@app/constants/locales/group';
import { members } from '@app/constants/locales/members';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { GroupInfoDto, ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';
import { useCreateRespondersGroupMutation, useUpdateResponderGroupMutation } from '@app/store/workspaces/api';
import { WorkspaceState } from '@app/store/workspaces/slice';

export default function CreateGroupModal({ responderGroup, email }: { responderGroup: ResponderGroupDto; email: string }) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const workspace = useAppSelector((state: { workspace: WorkspaceState & PersistPartial }) => state.workspace);
    const [groupInfo, setGroupInfo] = useState<GroupInfoDto>({
        name: responderGroup?.name ?? '',
        description: responderGroup?.description ?? '',
        email: '',
        emails: email ? [email] : responderGroup?.emails ?? []
    });
    const [createResponderGroup, createGroupResponse] = useCreateRespondersGroupMutation();
    const [updateResponderGroup, updateGroupResponse] = useUpdateResponderGroupMutation();
    const handleInput = (event: any) => {
        setGroupInfo({
            ...groupInfo,
            [event.target.id]: event.target.value
        });
    };
    console.log(groupInfo);
    const addEmail = (event: any) => {
        event.preventDefault();
        let emails = groupInfo.emails;
        if (!groupInfo.emails.includes(groupInfo.email)) {
            emails = [...emails, groupInfo.email];
            setGroupInfo({
                ...groupInfo,
                email: '',
                emails: emails
            });
        } else {
            toast(t(toastMessage.emailAlreadyExist).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'error' });
        }
    };
    const handleUpdateGroup = async () => {
        const response: any = await updateResponderGroup({
            groupInfo: groupInfo,
            workspaceId: workspace.id,
            groupId: responderGroup.id
        });
        if (response?.data) {
            toast(t(toastMessage.updated).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            closeModal();
        } else {
            toast(response?.error?.message || t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    const handleGroupButton = () => {
        if (responderGroup) {
            handleUpdateGroup();
        } else {
            handleCreateGroup();
        }
    };

    const handleCreateGroup = async () => {
        const response: any = await createResponderGroup({
            groupInfo: groupInfo,
            workspace_id: workspace.id
        });
        if (response?.data) {
            toast(t(toastMessage.workspaceSuccess).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            closeModal();
        } else {
            toast(response?.error?.message || t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };

    return (
        <div className="p-7 bg-brand-100 relative rounded-[8px] md:w-[670px]">
            <Close
                className="absolute top-5 right-5 cursor-pointer"
                onClick={() => {
                    closeModal();
                }}
            />
            <h4 className="h4 !leading-none">{responderGroup ? t(groupConstant.editGroup) : t(groupConstant.createNewGroup.default)}</h4>
            {!responderGroup && <p className="body4 leading-none mt-5  text-black-700">{t(groupConstant.createNewGroup.description)}</p>}
            <p className="body4 mt-10 leading-none mb-2">
                {t(groupConstant.name)}
                <span className="text-red-800">*</span>
            </p>
            <BetterInput value={groupInfo.name} className="!mb-0" inputProps={{ className: '!py-3' }} id="name" placeholder={t(placeHolder.groupName)} onChange={handleInput} />
            <p className="body4 leading-none mt-6 mb-2">{t(localesGlobal.description)}</p>
            <BetterInput value={groupInfo.description} className="!mb-0" inputProps={{ maxLength: 250 }} id="description" placeholder={t(placeHolder.description)} rows={3} multiline onChange={handleInput} />
            <p className="mt-10 leading-none mb-2 body1">
                {groupInfo.emails.length > 1 ? t(members.default) : t(members.member)} ({groupInfo.emails.length})
            </p>
            <p className="text-black-700 leading-none body4">{t(groupConstant.members.description)} </p>
            <form onSubmit={addEmail} className="flex gap-2 mt-4">
                <div className="md:w-[260px]">
                    <BetterInput value={groupInfo.email} type="email" inputProps={{ className: '!py-3 ' }} id="email" placeholder={t(placeHolder.memberEmail)} onChange={handleInput} />
                </div>
                <Button size="medium" disabled={!groupInfo.email} className={cn('bg-black-800 hover:!bg-black-900', !groupInfo.email && 'opacity-30')}>
                    {t(buttonConstant.add)}
                </Button>
            </form>
            {groupInfo.emails.length !== 0 && (
                <div>
                    <p className="mt-6 leading-none mb-4 body5">{t(groupConstant.memberEmail)}</p>
                    <div className="items-center  w-full p-3 bg-white   gap-4 flex flex-wrap ">
                        {groupInfo.emails.map((email) => {
                            return (
                                <div className="p-2 rounded flex items-center gap-2 leading-none bg-brand-200 body5 !text-brand-500" key={email}>
                                    <span className="leading-none">{email}</span>
                                    <Close
                                        className="h-4 w-4 cursor-pointer"
                                        onClick={() => {
                                            setGroupInfo({
                                                ...groupInfo,
                                                emails: groupInfo.emails.filter((item) => item !== email)
                                            });
                                        }}
                                    />
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
            <div className="flex justify-end mt-10">
                <Button size="medium" disabled={!groupInfo.name || groupInfo.emails.length === 0} isLoading={responderGroup ? createGroupResponse.isLoading : updateGroupResponse.isLoading} onClick={handleGroupButton}>
                    <span className="body1 !text-blue-100">{responderGroup ? t(buttonConstant.saveChanges) : t(groupConstant.createGroup)} </span>
                </Button>
            </div>
        </div>
    );
}
