'use client';

import { useEffect, useState } from 'react';

import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import { useAppSelector } from '@app/store/hooks';
import { useAddPhotoInWorkspaceMediaLibraryMutation, useGetWorkspaceMediaLibraryQuery, useLazyGetWorkspaceMediaLibraryQuery } from '@app/store/media-library/api';
import { MediaLibrary } from '@app/store/media-library/type';
import { selectWorkspace } from '@app/store/workspaces/slice';
import EmptyGallerIcon from '@app/views/atoms/Icons/EmptyGalleryIcon';
import { toast } from 'react-toastify';
import MediaItem from './MediaItem';
import SearchBar from './PhotoSearch';

const UploadMediaComponent = ({ updatePageImage }: { updatePageImage: (args: any) => void }) => {
    const [query, setQuery] = useState('');
    const workspace = useAppSelector(selectWorkspace);

    const { data, isLoading } = useGetWorkspaceMediaLibraryQuery({ workspace_id: workspace.id });
    const [addPhotoInLibrary] = useAddPhotoInWorkspaceMediaLibraryMutation();
    const [searchPhoto, { isLoading: isSeaching }] = useLazyGetWorkspaceMediaLibraryQuery();
    const [loading, setLoading] = useState(isLoading || isSeaching);

    useEffect(() => {
        setLoading(isLoading || isSeaching);
    }, [isLoading, isSeaching]);

    const [medias, setMedias] = useState<Array<MediaLibrary>>(data ? data : []);
    useEffect(() => {
        data && setMedias(data);
    }, [data]);

    const handleAddMedia = (e: any) => {
        e.preventDefault();
        const file = e.target.files[0];
        const formData = new FormData();
        formData.append('file', file);
        file && setMedias([{ mediaId: 'id', mediaType: '', mediaName: '', mediaUrl: '', workspaceId: '' }, ...medias]);
        addPhotoInLibrary({ workspace_id: workspace.id, media: formData }).then((result: any) => {
            if (result.data) {
                updatePageImage(result.data.mediaUrl);
            } else {
                toast(result?.error?.data, {
                    type: 'error'
                });
            }
        });
    };

    return (
        <>
            <div className="mr-2 flex h-[430px] flex-col">
                <div className="flex flex-col items-start justify-between gap-2 md:flex-row md:items-center">
                    <SearchBar
                        onSearch={(query: string) =>
                            searchPhoto({ workspace_id: workspace.id, media_query: query }).then((result: any) => {
                                if (result.data) {
                                    setMedias(result.data);
                                }
                            })
                        }
                        query={query}
                        setQuery={setQuery}
                    />
                    <label htmlFor="upload-media" className="bg-new-black-800 hover:bg-new-black-900 flex !h-9 cursor-pointer items-center justify-center rounded px-4 py-2 text-white">
                        <span className="p3-new"> Upload New</span>
                    </label>
                    <input type="file" hidden id="upload-media" onChange={handleAddMedia} accept="image/*" />
                </div>
                {loading && <SkeletonLoadingComponent />}

                {!loading && Array.isArray(medias) && medias.length ? (
                    <div className="max-h-media-library col mt-6 grid grid-cols-2 gap-4 overflow-auto">
                        <div className="flex flex-col gap-4">
                            {medias.map((media: MediaLibrary, index: number) => {
                                if (index % 2 === 0) {
                                    return <MediaItem key={media.mediaId} media={media} updatePageImage={updatePageImage} />;
                                } else return <></>;
                            })}
                        </div>
                        <div className="flex flex-col gap-4">
                            {medias.map((media: MediaLibrary, index: number) => {
                                if (index % 2 !== 0) {
                                    return <MediaItem key={media.mediaId} media={media} updatePageImage={updatePageImage} />;
                                } else return <></>;
                            })}
                        </div>
                    </div>
                ) : (
                    <div className="flex h-full flex-col items-center justify-start gap-2 py-20">
                        {!loading && (
                            <>
                                <EmptyGallerIcon />
                                <span className="p4-new text-black-600">No images uploaded yet</span>
                            </>
                        )}
                    </div>
                )}
            </div>
        </>
    );
};

export default UploadMediaComponent;

export const SkeletonLoadingComponent = ({ quantity = 4 }: { quantity?: number }) => {
    return (
        <div className="mt-4 grid h-fit w-full grid-cols-2 items-center justify-center gap-2 overflow-hidden">
            {[...Array(quantity)].map((index: number) => {
                return <Skeleton key={index} className="bg-black-300 h-[140px] pb-10" />;
            })}
        </div>
    );
};
