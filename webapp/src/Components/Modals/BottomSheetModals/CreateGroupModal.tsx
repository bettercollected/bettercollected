import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import BottomSheetModalWrapper from '@Components/Modals/ModalWrappers/BottomSheetModalWrapper';
import { toast } from 'react-toastify';

import RegexCard from '@app/components/cards/regex-card';
import GroupInfo from '@app/components/group/group-info';
import GroupMember from '@app/components/group/group-member';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { groupConstant } from '@app/constants/locales/group';
import { members } from '@app/constants/locales/members';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { GroupInfoDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { handleRegexType } from '@app/models/enums/groupRegex';
import { useAppSelector } from '@app/store/hooks';
import { useCreateRespondersGroupMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function CreateGroupModal() {
    const router = useRouter();
    let formId: string = (router?.query?.formId as string) ?? '';
    const { closeBottomSheetModal } = useBottomSheetModal();
    const { t } = useTranslation();
    const { closeModal } = useModal();
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const [groupInfo, setGroupInfo] = useState<GroupInfoDto>({
        name: '',
        description: '',
        emails: [],
        regex: '',
        formId: formId ?? ''
    });
    const [createResponderGroup, { isLoading }] = useCreateRespondersGroupMutation();
    const handleInput = (event: any) => {
        setGroupInfo({
            ...groupInfo,
            [event.target.id]: event.target.value
        });
    };

    const handleRegex = (regex: string, type: handleRegexType) => {
        if (type === handleRegexType.ADD) {
            setGroupInfo({
                ...groupInfo,
                regex
            });
            closeModal();
        } else if (type === handleRegexType.REMOVE) {
            setGroupInfo({
                ...groupInfo,
                regex: ''
            });
        }
    };

    const handleCreateGroup = async () => {
        try {
            await createResponderGroup({
                groupInfo: groupInfo,
                workspace_id: workspace.id
            }).then((response) => {
                if ('data' in response) {
                    toast(t(toastMessage.workspaceSuccess).toString(), {
                        toastId: ToastId.SUCCESS_TOAST,
                        type: 'success'
                    });
                    closeBottomSheetModal();
                } else
                    toast(t(toastMessage.somethingWentWrong).toString(), {
                        toastId: ToastId.ERROR_TOAST,
                        type: 'error'
                    });
            });
        } catch (error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };

    const handleAddMembers = (members: Array<string>) => {
        if (groupInfo.emails) {
            setGroupInfo({
                ...groupInfo,
                emails: [...groupInfo.emails, ...members]
            });
            closeModal();
        } else {
            toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };

    const handleRemoveMember = (email: string) => {
        setGroupInfo({
            ...groupInfo,
            emails: groupInfo.emails?.filter((groupInfoEmail) => groupInfoEmail !== email)
        });
    };

    return (
        <BottomSheetModalWrapper>
            <div>
                <div className="h2-new mb-2">{t(groupConstant.createGroup)}</div>
                <div className="p2-new text-black-700">Create a group to limit access to form from your workspace</div>
            </div>
            <div className="flex flex-col md:max-w-[700px] xl:max-w-[1000px]">
                <div className="md:max-w-[618px]">
                    <div className="flex flex-col pt-16 gap-12">
                        <GroupInfo handleInput={handleInput} groupInfo={groupInfo} />
                        <div>
                            <RegexCard handleRegex={handleRegex} regex={groupInfo.regex} />
                            {groupInfo.emails && <GroupMember emails={groupInfo.emails} handleAddMembers={handleAddMembers} handleRemoveMember={handleRemoveMember} />}
                        </div>
                        <div>
                            <AppButton isLoading={isLoading} variant={ButtonVariant.Secondary} disabled={!groupInfo.name || (groupInfo.emails?.length === 0 && groupInfo.regex?.length === 0)} onClick={handleCreateGroup}>
                                {t(buttonConstant.saveGroup)}
                            </AppButton>
                        </div>
                    </div>
                </div>
            </div>
        </BottomSheetModalWrapper>
    );
}
