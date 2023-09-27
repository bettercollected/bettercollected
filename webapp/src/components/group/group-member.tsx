import React from 'react';

import {useTranslation} from 'next-i18next';

import SearchInput from '@Components/Common/Search/SearchInput';

import MemberCard from '@app/components/cards/member-card';
import {Plus} from '@app/components/icons/plus';
import {useModal} from '@app/components/modal-views/context';
import {buttonConstant} from '@app/constants/locales/button';
import {groupConstant} from '@app/constants/locales/group';
import {ResponderGroupDto} from '@app/models/dtos/groups';
import {selectIsAdmin} from '@app/store/auth/slice';
import {useAppSelector} from '@app/store/hooks';
import AppButton from "@Components/Common/Input/Button/AppButton";
import {ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";

interface IGroupMemberProps {
    group?: ResponderGroupDto;
    emails: Array<string>;
    handleSearch?: (event: any) => void;
    handleAddMembers: (members: Array<string>) => void;
    handleRemoveMember: (email: string) => void;
}

export default function GroupMember({
                                        group,
                                        emails,
                                        handleSearch,
                                        handleAddMembers,
                                        handleRemoveMember
                                    }: IGroupMemberProps) {
    const {openModal} = useModal();
    const {t} = useTranslation();
    const isAdmin = useAppSelector(selectIsAdmin);
    const MemberList = () => (
        <div className=" mt-6 flex flex-col md:max-w-[610px] gap-6">
            {!!handleSearch && (
                <div className="sm:w-[240px]">
                    <SearchInput handleSearch={handleSearch}/>
                </div>
            )}
            <div className="flex flex-col gap-2">
                {emails.map((email) => (
                    <MemberCard key={email} email={email} onDeleteClick={() => handleRemoveMember(email)}/>
                ))}
            </div>
        </div>
    );
    const handleMemberList = () => {
        if ((handleSearch && group && group.emails && group.emails.length > 0) || emails.length > 0) return MemberList();
    };
    return (
        <>
            <div className="flex flex-col md:flex-row items-center justify-between">
                <div className="flex flex-col">
                    <p className="mt-10 leading-none mb-2 body1">
                        {t(groupConstant.memberAdded)} ({group?.emails?.length || emails.length || 0})
                    </p>
                    <p className="text-black-700 leading-none body4">{t(groupConstant.members.description)} </p>
                </div>
                {isAdmin && (
                    <AppButton variant={ButtonVariant.Ghost} icon={<Plus className="h-4 w-4"/>}
                               onClick={() => openModal('ADD_MEMBERS', {handleAddMembers, group})}>

                        {t(buttonConstant.addMember)}
                    </AppButton>
                )}
            </div>

            {handleMemberList()}
        </>
    );
}
