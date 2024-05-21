'use client';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { useSecondaryDialogModal } from '@app/lib/hooks/useSecondaryDialogModal';
import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { MediaLibrary } from '@app/store/media-library/type';
import { selectWorkspace } from '@app/store/workspaces/slice';
import DeleteIcon from '@app/views/atoms/Icons/Delete';
import Image from 'next/image';
import { useState } from 'react';

const MediaItem = ({ media, updatePageImage }: { media: MediaLibrary; updatePageImage: (args: any) => void }) => {
    const workspace = useAppSelector(selectWorkspace);
    const { closeDialogModal } = useDialogModal();
    const { openSecondaryDialogModal } = useSecondaryDialogModal();

    const handleDeleteMedia = (mediaId: string) => {
        openSecondaryDialogModal('DELETE_MEDIA', { workspace_id: workspace.id, media_id: mediaId });
    };
    if (!media.mediaName && !media.mediaType) return <Skeleton className="bg-black-300 inset-0 h-[200px] w-full pb-10" />;
    return (
        <div className="group relative h-auto cursor-pointer overflow-hidden" key={media.mediaId}>
            <ImageWithLoader media={media} />
            <div
                className="absolute inset-0 z-[1000] hidden h-full w-full items-end justify-center transition-all duration-300 group-hover:flex group-hover:bg-black/60 md:p-4"
                onClick={() => {
                    updatePageImage(media.mediaUrl);
                    closeDialogModal();
                }}
            >
                <span className="p4-new text-white">{media.mediaName}</span>
            </div>
            <div className="invisible absolute right-2 top-2 z-[10000] group-hover:visible ">
                <div className="shadow-bubble cursor-pointer rounded-md bg-white p-2" onClick={() => handleDeleteMedia(media.mediaId)}>
                    <DeleteIcon width={14} height={14} />
                </div>
            </div>
        </div>
    );
};

const ImageWithLoader = ({ media }: { media: MediaLibrary }) => {
    const [nextImageLoading, setNextImageLoading] = useState(true);

    return (
        <div className={cn(`h-full w-full`)}>
            <Image
                className=" cursor-pointer"
                src={media.mediaUrl}
                alt={media.mediaName}
                priority
                width={0}
                height={0}
                sizes="100vw"
                onLoadingComplete={() => {
                    setNextImageLoading(false);
                }}
                style={{ objectFit: 'cover', width: '100%', height: 'auto' }}
            />
            {nextImageLoading && <Skeleton className=" bg-black-300 z-[10] h-[200px] w-full" />}
        </div>
    );
};

export default MediaItem;
