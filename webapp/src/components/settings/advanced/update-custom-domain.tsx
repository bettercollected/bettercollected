import React, { ChangeEvent, FormEvent, useState } from 'react';

import { useRouter } from 'next/router';

import { handle } from 'mdast-util-to-markdown/lib/handle';

import BetterInput from '@app/components/Common/input';
import { useModal } from '@app/components/modal-views/context';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';

export default function UpdateCustomDomain() {
    const workspace = useAppSelector((state) => state.workspace);
    const { openModal } = useModal();
    const router = useRouter();
    const isProPlan = useAppSelector(selectIsProPlan);

    const handleClick = () => {
        if (isProPlan) {
            openModal('UPDATE_WORKSPACE_DOMAIN');
        } else {
            router.push(`/${workspace.workspaceName}/upgrade`);
        }
    };

    return (
        <SettingsCard>
            <div className="body1">Custom Domain</div>
            <div className="flex w-full justify-between">
                <div className="w-full text-sm text-gray-600">
                    {workspace.customDomain ? (
                        <>
                            Your Custom Domain is currently set to <span className="font-bold"> {workspace.customDomain}.</span>
                        </>
                    ) : (
                        'You have not set up custom domain.'
                    )}
                </div>
                <div>
                    <Button onClick={handleClick}>Update</Button>
                </div>
            </div>
        </SettingsCard>
    );
}
