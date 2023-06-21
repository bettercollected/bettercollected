import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import GroupMember from '@app/components/group/group-member';
import { useModal } from '@app/components/modal-views/context';
import { localesCommon } from '@app/constants/locales/common';
import { useGroupMember } from '@app/lib/hooks/use-group-members';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

export default function GroupMembersTab({ group, workspace }: { group: ResponderGroupDto; workspace: WorkspaceDto }) {
    const [emails, setEmails] = useState(group.emails);
    const { t } = useTranslation();
    const { openModal } = useModal();
    const [searchQuery, setSearchQuery] = useState('');
    const handleSearch = (event: any) => {
        const query = event.target.value.toLowerCase();
        setSearchQuery(query);
    };
    const { addMembersOnGroup, removeMemberFromGroup } = useGroupMember();

    const handleAddmembers = (members: Array<string>) => addMembersOnGroup({ emails: members, group, workspaceId: workspace.id });

    const handleRemoveMembers = (email: string) => {
        openModal('DELETE_CONFIRMATION', { title: t(localesCommon.remove) + ' ' + email, handleDelete: () => removeMemberFromGroup({ email, group, workspaceId: workspace.id }) });
    };
    useEffect(() => {
        const filteredEmails = group.emails.filter((email) => {
            return email.toLowerCase().includes(searchQuery);
        });
        setEmails(filteredEmails);
    }, [searchQuery, group]);
    useEffect(() => {
        setEmails(group.emails);
    }, [group]);
    return (
        <div className="md:max-w-[618px] ">
            <GroupMember group={group} emails={emails} handleSearch={handleSearch} handleAddMembers={handleAddmembers} handleRemoveMember={handleRemoveMembers} />
        </div>
    );
}
