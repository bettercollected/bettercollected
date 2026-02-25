
import { useTranslation } from 'next-i18next';

import { Close } from '@app/components/icons/close';
import editWorkspace from '@app/constants/locales/edit-workpsace';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { useAppSelector } from '@app/store/hooks';
import WorkspaceBanner from '@Components/settings/workspace-banner';
import WorkspaceInfo from '@Components/settings/workspace-info';

import { useModal } from '../context';


export default function EditWorkspaceModal() {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const workspace: WorkspaceDto = useAppSelector((state) => state.workspace);
    return (
        <div className="p-7 bg-white relative rounded-[8px]">
            <Close
                className="absolute top-5 right-5 cursor-pointer"
                onClick={() => {
                    closeModal();
                }}
            />
            <h4 className="h4 text-black-900">{t(editWorkspace.title)}</h4>
            {/*<p className="body4 text-black-700">{t(editWorkspace.description)}</p>*/}
            <WorkspaceBanner />

            <WorkspaceInfo workspace={workspace} />
        </div>
    );
}