import React from 'react';

import UnsplashPhotoCard from './PhotoCard';
import { SkeletonLoadingComponent } from './UploadMediaComponent';

interface Props {
    isLoading?: boolean;
    isLoadingMore?: boolean;
    photoList: Array<any>;
    total?: number | undefined;
    onPhotoSelect: (photo: any) => void;
    loadMore: () => void;
}
function PhotoList({ isLoading = false, isLoadingMore = false, photoList, total, onPhotoSelect, loadMore }: Props) {
    const listHeight = '365px'; // 'calc(100 - 125px)'
    const ref = React.useMemo(() => React.createRef<HTMLDivElement>(), []);

    const onScroll = () => {
        if (ref.current) {
            const { scrollTop, scrollHeight, clientHeight } = ref.current;
            if (scrollHeight - (scrollTop + clientHeight) < 20) {
                // Contributors list lazy loading you're at the bottom of the page
                // do this when we reach end
                loadMore();
            }
        }
    };

    return (
        <div className="Body h-full w-full">
            {isLoading ? (
                <div className="flex h-full w-full items-center justify-center">
                    <SkeletonLoadingComponent />
                </div>
            ) : (
                <div>
                    {Array.isArray(photoList) && photoList.length > 0 && (
                        <div className="PhotoList grid grid-cols-1 gap-2 overflow-y-auto pb-12 sm:grid-cols-2 md:grid-cols-3" style={{ maxHeight: listHeight }} ref={ref} onScroll={onScroll}>
                            {photoList.map((photo: any) => {
                                return <UnsplashPhotoCard key={photo.id} photo={photo} onPhotoSelect={onPhotoSelect} />;
                            })}
                            {isLoadingMore && (
                                <div className="my-4 flex justify-center sm:col-span-2 md:col-span-3">
                                    <Loader />
                                </div>
                            )}
                        </div>
                    )}
                    {Array.isArray(photoList) && photoList.length === 0 && total === 0 && <div className="flex h-96 items-center justify-center">No photos found</div>}
                    {typeof total === 'undefined' && <div className="flex h-96 items-center justify-center text-gray-600" />}
                </div>
            )}
        </div>
    );
}
export function Loader() {
    return (
        <svg className="text-blue -ml-1 mr-3 h-5 w-5 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
    );
}
export default PhotoList;
