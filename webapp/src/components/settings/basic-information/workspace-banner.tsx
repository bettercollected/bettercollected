import { useRef, useState } from 'react';

import html2canvas from 'html2canvas';
import { toast } from 'react-toastify';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import SettingsCard from '@app/components/settings/card';
import { ToastId } from '@app/constants/toastId';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';

export default function WorkspaceBanner() {
    const workspace: WorkspaceDto = useAppSelector((state) => state.workspace);
    return (
        <SettingsCard className="!mt-5">
            <div className="body1">Workspace Banner</div>
            <div className="w-full">
                <BannerImageComponent workspace={workspace} isFormCreator={true} />
            </div>
        </SettingsCard>
    );
}
