import React from 'react';

import UserMore from '@app/components/icons/user-more';

import { useModal } from '../modal-views/context';
import Button from '../ui/button/button';

export default function WorkspaceGropus() {
    const { openModal } = useModal();
    const emptyGroup = () => (
        <div className="my-[119px] flex flex-col items-center">
            <UserMore />
            <p className="body1">Create a group to :</p>
            <ul className="list-disc body4 text-black-700 flex flex-col gap-4 mt-4">
                <li>Limit access to form from your workspace</li>
                <li>Send forms to multiple people at the same time</li>
            </ul>
            <Button className="mt-6" size="small" onClick={() => openModal('CREATE_GROUP')}>
                Create New Group
            </Button>
        </div>
    );
    return emptyGroup();
}
