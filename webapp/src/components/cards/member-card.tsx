import React from 'react';

import DeleteDropDown from '@app/components/ui/delete-dropdown';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

interface IMemberCardProps {
    email: string;
    onDeleteClick: () => void;
    bg?: string;
}

export default function MemberCard({ email, onDeleteClick, bg = 'white' }: IMemberCardProps) {
    const isAdmin = useAppSelector(selectIsAdmin);

    return (
        <div className={`flex justify-between body4 bg-${bg} px-4  rounded py-3 items-center !text-black-800`}>
            <span>{email}</span>
            {isAdmin && <DeleteDropDown onDropDownItemClick={onDeleteClick} className="z-[2000000000]" />}
        </div>
    );
}