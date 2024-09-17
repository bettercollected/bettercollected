import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { useSecondaryDialogModal } from '@app/lib/hooks/useSecondaryDialogModal';
import { Separator } from '@app/shadcn/components/ui/separator';
import { useDeletePhotoFromWorkspaceMediaLibraryMutation } from '@app/store/media-library/api';

const DeleteMediaModal = ({ workspace_id, media_id }: { workspace_id: string; media_id: string }) => {
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
            <span className=" text-black-800 p-2 font-medium">Delete Media</span>
            <Separator />
            <div className="flex flex-col gap-2 px-6 py-4">
                <span className="p2-new">Are you sure you want to delete?</span>
                <span className="p4-new text-black-600">Deleting this media will break the layout of all pages and forms using this image.</span>
                <div className="mt-2 flex flex-row gap-6">
                    <AppButton size={ButtonSize.Medium} className="w-full" variant={ButtonVariant.Secondary} onClick={() => closeSecondaryDialogModal()}>
                        Cancel
                    </AppButton>
                    <AppButton size={ButtonSize.Medium} className="w-full" isLoading={isLoading} variant={ButtonVariant.Danger} onClick={handleClickDelete}>
                        Delete
                    </AppButton>
                </div>
            </div>
        </div>
    );
};

export default DeleteMediaModal;
