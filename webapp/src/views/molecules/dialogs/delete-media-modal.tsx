import { useTranslation } from 'react-i18next';

import { useSecondaryDialogModal } from '@app/lib/hooks/use-secondary-dialog-modal';
import { Button } from '@app/shadcn/components/ui/button';
import { Separator } from '@app/shadcn/components/ui/separator';
import { useDeletePhotoFromWorkspaceMediaLibraryMutation } from '@app/store/media-library/api';

const DeleteMediaModal = ({ workspace_id, media_id }: { workspace_id: string; media_id: string }) => {
    const { t } = useTranslation('builder');
    const { closeSecondaryDialogModal } = useSecondaryDialogModal();
    const [deletePhotoInLibrary, { isLoading }] = useDeletePhotoFromWorkspaceMediaLibraryMutation();
    const handleClickDelete = () => {
        deletePhotoInLibrary({
            workspace_id,
            media_id
        }).then(() => closeSecondaryDialogModal());
    };

    return (
        <div className="flex h-full w-full flex-col">
            <span className=" text-black-800 p-2 font-medium">{t('MEDIA.DELETE_TITLE')}</span>
            <Separator />
            <div className="flex flex-col gap-2 px-6 py-4">
                <span className="p2-new">{t('MEDIA.DELETE_CONFIRM')}</span>
                <span className="p4-new text-black-600">{t('MEDIA.DELETE_WARNING')}</span>
                <div className="mt-2 flex flex-row gap-6">
                    <Button size="medium" className="w-full" variant="secondary" onClick={() => closeSecondaryDialogModal()}>
                        {t('MEDIA.CANCEL')}
                    </Button>
                    <Button size="medium" className="w-full" isLoading={isLoading} variant="danger" onClick={handleClickDelete}>
                        {t('MEDIA.DELETE')}
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default DeleteMediaModal;
