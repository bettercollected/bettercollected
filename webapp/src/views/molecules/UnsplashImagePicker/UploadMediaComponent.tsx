'use client';

import { useEffect, useState } from 'react';

import { useAppSelector } from '@app/store/hooks';
import { useAddPhotoInWorkspaceMediaLibraryMutation, useDeletePhotoFromWorkspaceMediaLibraryMutation, useLazyGetWorkspaceMediaLibraryQuery, useGetWorkspaceMediaLibraryQuery } from '@app/store/media-library/api';
import { MediaLibrary } from '@app/store/media-library/type';
import { selectWorkspace } from '@app/store/workspaces/slice';
import CircularProgressBar from '@app/views/atoms/Loaders/CircularLoadingAnimation';
import MediaList from './MediaList';
import SearchBar from './PhotoSearch';

const UploadMediaComponent = ({ updatePageImage }: { updatePageImage: (args: any) => void }) => {
    const [query, setQuery] = useState('');
    const workspace = useAppSelector(selectWorkspace);

    const { data, isLoading } = useGetWorkspaceMediaLibraryQuery({ workspace_id: workspace.id });
    const [addPhotoInLibrary, { isLoading: isAddPhotoInMediaLoading }] = useAddPhotoInWorkspaceMediaLibraryMutation();
    const [deletePhotoInLibrary, { isLoading: isDeletePhotoInMediaLoading }] = useDeletePhotoFromWorkspaceMediaLibraryMutation();
    const [searchPhoto, { isLoading: isSeaching }] = useLazyGetWorkspaceMediaLibraryQuery();

    const [medias, setMedias] = useState<Array<MediaLibrary>>(data ? data : []);
    // useEffect(() => {
    //     data && setMedias(data);
    // }, [data]);

    const handleAddMedia = (e: any) => {
        e.preventDefault();
        const file = e.target.files[0];
        const formData = new FormData();
        formData.append('file', file);
        addPhotoInLibrary({ workspace_id: workspace.id, media: formData }).then((result: any) => {
            updatePageImage(result.data.mediaUrl);
        });
    };

    console.log('assssss', Array.isArray(medias));

    return (
        <>
            <div className="mb-6 mr-2 flex h-[405px] flex-col">
                <div className="flex flex-col items-center justify-between md:flex-row">
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
                    <label htmlFor="upload-media" className="bg-new-black-800 flex !h-9 cursor-pointer items-center justify-center rounded px-4 py-2 text-white">
                        <span className="p3-new"> Upload New</span>
                    </label>
                    <input type="file" hidden id="upload-media" onChange={handleAddMedia} />
                </div>
                {(isLoading || isAddPhotoInMediaLoading || isDeletePhotoInMediaLoading || isSeaching) && (
                    <div className="flex h-full w-full items-center justify-center">
                        <CircularProgressBar className="h-10 w-10" />
                    </div>
                )}

                {!isAddPhotoInMediaLoading && !isDeletePhotoInMediaLoading && !isSeaching && Array.isArray(medias) && medias.length ? (
                    <div className="max-h-media-library mt-6 grid grid-cols-2 justify-end gap-4 overflow-auto">
                        {medias.map((media: MediaLibrary) => {
                            return <MediaList media={media} updatePageImage={updatePageImage} deletePhotoInLibrary={deletePhotoInLibrary} />;
                        })}
                    </div>
                ) : (
                    <div className="flex h-full items-center justify-center">{!isAddPhotoInMediaLoading && !isDeletePhotoInMediaLoading && !isSeaching && <span>No Images Uploaded yet.</span>}</div>
                )}
            </div>
        </>
    );
};

export default UploadMediaComponent;
