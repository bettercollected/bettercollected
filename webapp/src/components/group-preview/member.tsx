import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import SearchInput from '@Components/Common/Search/SearchInput';
import { Typography } from '@mui/material';

import MemberCard from '@app/components/cards/member-card';
import RegexCard from '@app/components/cards/regex-card';
import { Plus } from '@app/components/icons/plus';
import { useModal } from '@app/components/modal-views/context';
import DeleteDropDown from '@app/components/ui/delete-dropdown';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { members } from '@app/constants/locales/members';
import { useGroupMember } from '@app/lib/hooks/use-group-members';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

export default function GroupMembers({ group, workspace }: { group: ResponderGroupDto; workspace: WorkspaceDto }) {
    const { t } = useTranslation();
    const { removeMemberFromGroup } = useGroupMember();
    const { openModal } = useModal();
    const [emails, setEmails] = useState(group.emails);
    const isAdmin = useAppSelector(selectIsAdmin);
    const [searchQuery, setSearchQuery] = useState('');
    const handleSearch = (event: any) => {
        const query = event.target.value.toLowerCase();
        setSearchQuery(query);
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
            <p className="leading-none mb-6 body1">{t(members.default)}</p>
            <RegexCard addRegex={() => {}} />
            <div className="flex items-center justify-between">
                <div className="flex flex-col">
                    <p className="mt-10 leading-none mb-2 body1">Members Added ({emails.length})</p>
                    <p className="text-black-700 leading-none body4">{t(groupConstant.members.description)} </p>
                </div>
                <div onClick={() => openModal('ADD_MEMBER')} className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                    <Plus className="h-4 w-4" />
                    <Typography className="!text-brand-500  body6">Add Member</Typography>
                </div>
            </div>
            {group.emails.length > 0 && (
                <div className=" mt-6 flex flex-col md:max-w-[610px] gap-6">
                    <div className="sm:w-[240px]">
                        <SearchInput handleSearch={handleSearch} />
                    </div>
                    <div className="flex flex-col gap-2">
                        {emails.map((email) => (
                            <MemberCard
                                key={email}
                                email={email}
                                onDeleteClick={() => openModal('DELETE_CONFIRMATION', { title: t(localesCommon.remove) + ' ' + email, handleDelete: () => removeMemberFromGroup({ email, group, workspaceId: workspace.id }) })}
                            />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
