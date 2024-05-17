'use client';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { useAppSelector } from '@app/store/hooks';
import { MediaLibrary } from '@app/store/media-library/type';
import { selectWorkspace } from '@app/store/workspaces/slice';
import DeleteIcon from '@app/views/atoms/Icons/Delete';
import Image from 'next/image';
import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import { useEffect, useState } from 'react';

const MediaItem = ({ media, deletePhotoInLibrary, updatePageImage, isAddPhotoInMediaLoading = false }: { media: MediaLibrary; deletePhotoInLibrary: (args: any) => void; updatePageImage: (args: any) => void; isAddPhotoInMediaLoading?: boolean }) => {
    const workspace = useAppSelector(selectWorkspace);
    const { closeDialogModal } = useDialogModal();
    const [nextImageLoading, setNextImageLoading] = useState(false);
    useEffect(() => {
        if (!isAddPhotoInMediaLoading) {
            setNextImageLoading(false);
        }
    }, [isAddPhotoInMediaLoading]);

    const handleDeleteMedia = (mediaId: string) => {
        deletePhotoInLibrary({ workspace_id: workspace.id, media_id: mediaId });
    };
    if (isAddPhotoInMediaLoading || nextImageLoading) return <Skeleton className="bg-black-300 inset-0 h-[130px] w-full pb-10" />;
    return (
        <div className="group relative h-auto cursor-pointer" key={media.mediaId}>
            <Image
                className="cursor-pointer"
                onClick={() => {
                    updatePageImage(media.mediaUrl);
                    closeDialogModal();
                }}
                src={media.mediaUrl}
                alt={media.mediaName}
                priority
                width={0}
                height={0}
                sizes="100vw"
                onLoad={() => isAddPhotoInMediaLoading && setNextImageLoading(true)}
                style={{ width: '100%', height: 'auto' }}
            />
            <div className="invisible absolute right-2 top-2 z-[10000] group-hover:visible">
                <div className="shadow-bubble cursor-pointer rounded-md bg-white p-2" onClick={() => handleDeleteMedia(media.mediaId)}>
                    <DeleteIcon width={14} height={14} />
                </div>
            </div>
        </div>
    );
};

export default MediaItem;
