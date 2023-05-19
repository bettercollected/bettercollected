import React from 'react';

import { useTranslation } from 'next-i18next';

import { useModal } from '@app/components/modal-views/context';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { advanceSetting } from '@app/constants/locales/advance-setting';
import { buttons } from '@app/constants/locales/buttons';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { useAppSelector } from '@app/store/hooks';

export default function UpdateHandle() {
    const workspace = useAppSelector((state) => state.workspace);
    const { openModal } = useModal();
    const { t } = useTranslation();

    const handleClick = () => {
        openModal('UPDATE_WORKSPACE_HANDLE');
    };

    return (
        <SettingsCard className="!mt-5">
            <div className="body1">{t(workspaceConstant.handle)}</div>
            <div className="flex w-full justify-between">
                <div className="w-full text-sm text-gray-600">
                    {t(advanceSetting.workspaceHandleDescription)}
                    <span className="font-bold"> {workspace.workspaceName}.</span>
                </div>
                <div>
                    <Button onClick={handleClick}>{t(buttons.update)}</Button>
                </div>
            </div>
        </SettingsCard>
    );
}
