import { useSecondaryDialogModal } from '@app/lib/hooks/useSecondaryDialogModal';
import { Button } from '@app/shadcn/components/ui/button';
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
                <span className="p4-new text-black-600">On deleting this media you will break the layout of every page in every form where this image is being used.</span>
                <div className="mt-2 flex flex-row justify-center gap-6">
                    <Button isLoading={isLoading} variant={'danger'} onClick={handleClickDelete}>
                        Delete
                    </Button>
                    <Button onClick={() => closeSecondaryDialogModal()}>Cancel</Button>
                </div>
            </div>
        </div>
    );
};

export default DeleteMediaModal;
