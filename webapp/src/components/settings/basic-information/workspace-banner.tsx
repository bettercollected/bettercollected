import { useRef, useState } from 'react';

import { useTranslation } from 'next-i18next';

import html2canvas from 'html2canvas';
import { toast } from 'react-toastify';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import SettingsCard from '@app/components/settings/card';
import { workspaceConstant } from '@app/constants/locales';
import { ToastId } from '@app/constants/toastId';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';

export default function WorkspaceBanner() {
    const workspace: WorkspaceDto = useAppSelector((state) => state.workspace);
    const { t } = useTranslation();
    return (
        <SettingsCard className="!mt-5">
            <div className="body1">{t(workspaceConstant.banner)}</div>
            <div className="w-full">
                <BannerImageComponent workspace={workspace} isFormCreator={true} />
            </div>
        </SettingsCard>
    );
}
