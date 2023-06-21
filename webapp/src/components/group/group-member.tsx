import React from 'react';

import { useTranslation } from 'next-i18next';

import SearchInput from '@Components/Common/Search/SearchInput';
import { Typography } from '@mui/material';

import MemberCard from '@app/components/cards/member-card';
import RegexCard from '@app/components/cards/regex-card';
import { Plus } from '@app/components/icons/plus';
import { useModal } from '@app/components/modal-views/context';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { members } from '@app/constants/locales/members';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { useGroupMember } from '@app/lib/hooks/use-group-members';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface IGroupMemberProps {
    group?: ResponderGroupDto;
    emails: Array<string>;
    handleSearch?: (event: any) => void;
    handleAddMembers: (members: Array<string>) => void;
    handleRemoveMember: (email: string) => void;
}
export default function GroupMember({ group, emails, handleSearch, handleAddMembers, handleRemoveMember }: IGroupMemberProps) {
    const { openModal } = useModal();
    const { t } = useTranslation();

    const MemberList = () => (
        <div className=" mt-6 flex flex-col md:max-w-[610px] gap-6">
            {!!handleSearch && (
                <div className="sm:w-[240px]">
                    <SearchInput handleSearch={handleSearch} />
                </div>
            )}
            <div className="flex flex-col gap-2">
                {emails.map((email) => (
                    <MemberCard key={email} email={email} onDeleteClick={() => handleRemoveMember(email)} />
                ))}
            </div>
        </div>
    );
    const handleMemberList = () => {
        if ((handleSearch && group && group.emails.length > 0) || emails.length > 0) return MemberList();
    };
    return (
        <div>
            <p className="leading-none mb-6 body1">{t(members.default)}</p>
            <RegexCard addRegex={() => {}} />
            <div className="flex items-center justify-between">
                <div className="flex flex-col">
                    <p className="mt-10 leading-none mb-2 body1">Members Added ({group?.emails.length || emails.length || 0})</p>
                    <p className="text-black-700 leading-none body4">{t(groupConstant.members.description)} </p>
                </div>
                <div onClick={() => openModal('ADD_MEMBER', { handleAddMembers, group })} className="flex gap-2 p-2  text-brand-500 items-center cursor-pointer">
                    <Plus className="h-4 w-4" />
                    <Typography className="!text-brand-500  body6">Add Member</Typography>
                </div>
            </div>
            {handleMemberList()}
        </div>
    );
}
