import React from 'react';

import DeleteDropDown from '@app/components/ui/delete-dropdown';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

interface IMemberCardProps {
    email: string;
    onDeleteClick: () => void;
}
export default function MemberCard({ email, onDeleteClick }: IMemberCardProps) {
    const isAdmin = useAppSelector(selectIsAdmin);

    return (
        <div className="flex  justify-between body4 bg-white px-4  rounded py-4 items-center !text-black-800">
            <span>{email}</span>
            {isAdmin && <DeleteDropDown onDropDownItemClick={onDeleteClick} />}
        </div>
    );
}
