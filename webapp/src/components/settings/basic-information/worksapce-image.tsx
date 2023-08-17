import React from 'react';

import { useTranslation } from 'next-i18next';

import ProfileImageComponent from '@app/components/dashboard/profile-image';
import SettingsCard from '@app/components/settings/card';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { useAppSelector } from '@app/store/hooks';

export default function WorkspaceImage() {
    const workspace = useAppSelector((state) => state.workspace);
    const { t } = useTranslation();

    return (
        <SettingsCard>
            <div className="body1">{t(workspaceConstant.profileImage)}</div>
            <div className="md:w-[350px] w-full ">
                <ProfileImageComponent workspace={workspace} isFormCreator={true} />
            </div>
        </SettingsCard>
    );
}
