import React from 'react';

import ProfileImageComponent from '@app/components/dashboard/profile-image';
import SettingsCard from '@app/components/settings/card';
import { useAppSelector } from '@app/store/hooks';

export default function WorkspaceImage() {
    const workspace = useAppSelector((state) => state.workspace);

    return (
        <SettingsCard>
            <div className="body1">Workspace Profile Image</div>
            <div className="w-40">
                <ProfileImageComponent workspace={workspace} isFormCreator={true} />
            </div>
        </SettingsCard>
    );
}
