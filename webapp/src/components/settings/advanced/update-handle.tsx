import React, { ChangeEvent, FormEvent, useState } from 'react';

import { handle } from 'mdast-util-to-markdown/lib/handle';

import BetterInput from '@app/components/common/input';
import { useModal } from '@app/components/modal-views/context';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';

export default function UpdateHandle() {
    const workspace = useAppSelector((state) => state.workspace);
    const { openModal } = useModal();

    const handleClick = () => {
        openModal('UPDATE_WORKSPACE_HANDLE');
    };

    return (
        <SettingsCard>
            <div className="body1">Workspace Handle</div>
            <div className="flex w-full justify-between">
                <div className="w-full text-sm text-gray-600">
                    Your workspace handle is currently set to <span className="font-bold"> {workspace.workspaceName}.</span>
                </div>
                <div>
                    <Button onClick={handleClick}>Update</Button>
                </div>
            </div>
        </SettingsCard>
    );
}
