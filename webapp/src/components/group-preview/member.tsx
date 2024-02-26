import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { toast } from 'react-toastify';

import RegexCard from '@app/components/cards/regex-card';
import GroupMember from '@app/components/group/group-member';
import { useModal } from '@app/components/modal-views/context';
import { localesCommon } from '@app/constants/locales/common';
import { members } from '@app/constants/locales/members';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useGroupMember } from '@app/lib/hooks/use-group-members';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { handleRegexType } from '@app/models/enums/groupRegex';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useUpdateResponderGroupMutation } from '@app/store/workspaces/api';


interface IGroupMemberTabProps {
    group: ResponderGroupDto;
    workspace: WorkspaceDto;
}

export default function GroupMembersTab({ group, workspace }: IGroupMemberTabProps) {
    const [emails, setEmails] = useState(group.emails);
    const { t } = useTranslation();
    const isAdmin = useAppSelector(selectIsAdmin);

    const { openModal, closeModal } = useModal();
    const [searchQuery, setSearchQuery] = useState('');
    const [patchRegex] = useUpdateResponderGroupMutation();
    const handleSearch = (event: any) => {
        const query = event.target.value.toLowerCase();
        setSearchQuery(query);
    };

    const { addMembersOnGroup, removeMemberFromGroup } = useGroupMember();

    const handleAddmembers = (members: Array<string>) =>
        addMembersOnGroup({
            emails: members,
            group,
            workspaceId: workspace.id
        });

    const handleRemoveMembers = (email: string) => {
        openModal('DELETE_CONFIRMATION', {
            headerTitle: 'Remove Member',
            title: t(localesCommon.remove) + ' ' + email,
            handleDelete: () => removeMemberFromGroup({ email, group, workspaceId: workspace.id })
        });
    };
    const handleRegex = async (regex: string, type: handleRegexType) => {
        const groupInfo = {
            regex: type === handleRegexType.REMOVE ? '' : regex
        };
        try {
            await patchRegex({
                groupInfo: groupInfo,
                workspaceId: workspace.id,
                groupId: group.id
            }).then((response) => {
                if (`data` in response) {
                    toast(t(toastMessage.updated).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
                    closeModal();
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
    useEffect(() => {
        const filteredEmails = group.emails?.filter((email) => {
            return email.toLowerCase().includes(searchQuery);
        });
        setEmails(filteredEmails);
    }, [searchQuery, group]);
    useEffect(() => {
        setEmails(group.emails);
    }, [group]);
    return (
        <div className="md:max-w-[618px] ">
            <div>
                <p className="leading-none mb-6 body1">{t(members.default)}</p>
                <RegexCard handleRegex={handleRegex} regex={group.regex ?? ''} />
                {emails && <GroupMember group={group} emails={emails} handleSearch={handleSearch} handleAddMembers={handleAddmembers} handleRemoveMember={handleRemoveMembers} />}
            </div>
        </div>
    );
}