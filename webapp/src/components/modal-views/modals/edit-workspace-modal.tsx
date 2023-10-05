import React from 'react';

import { useTranslation } from 'next-i18next';

import { Close } from '@app/components/icons/close';
import WorkspaceBanner from '@app/components/settings/basic-information/workspace-banner';
import WorkspaceInfo from '@app/components/settings/basic-information/workspace-info';
import editWorkspace from '@app/constants/locales/edit-workpsace';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';

import { useModal } from '../context';


export default function EditWorkspaceModal() {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const workspace: WorkspaceDto = useAppSelector((state) => state.workspace);
    return (
        <div className="p-7 bg-brand-100 relative rounded-[8px]">
            <Close
                className="absolute top-5 right-5 cursor-pointer"
                onClick={() => {
                    closeModal();
                }}
            />
            <h4 className="h4 text-black-900">{t(editWorkspace.title)}</h4>
            <p className="body4 text-black-700">{t(editWorkspace.description)}</p>
            <WorkspaceBanner />

            <WorkspaceInfo workspace={workspace} />
        </div>
    );
}