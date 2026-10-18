'use client';

import React from 'react';

import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';

import { Separator } from '@app/shadcn/components/ui/separator';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@app/views/organism/form-builder/add-slide/add-slice-tabs';
import PhotoList from './photo-list';
import SearchBar from './photo-search';
import UploadMediaComponent from './upload-media-comonent';

// as app/api/unsplash allows
const MAX_QUERY_LENGTH = 100;

// what the picker says when a search fails, by the route's status (0: no answer)
function searchErrorMessage(status: number): string {
    if (status === 401) return 'Sign in again to search images. You can still upload an image.';
    if (status === 429) return 'Too many image searches. Try again in a few minutes.';
    return 'Image search is unavailable right now. You can still upload an image.';
}

interface IUnsplashImagePickerProps {
    initialPhotoSearchQuery?: string;
    onPhotoSelect?: (photo: any) => void;

    [key: string]: any;
}

export default function UnsplashImagePicker({ initialPhotoSearchQuery = '', onPhotoSelect = (_: any) => { }, ...props }: IUnsplashImagePickerProps) {
    const [pics, setPics] = React.useState<any[]>([]);
    const [total, setTotal] = React.useState<number | undefined>();
    const [query, setQuery] = React.useState('');
    const [isLoading, setIsLoading] = React.useState(false);
    const [initialLoading, setInitialLoading] = React.useState(false);
    const [isLoadingMore, setIsLoadingMore] = React.useState(false);
    const [page, setPage] = React.useState(1);
    const [searchError, setSearchError] = React.useState<string | null>(null);
    const form = useAppSelector(selectForm);

    const { closeDialogModal } = useDialogModal();

    const updatePageImage = props?.updatePageImage ?? (() => { });

    React.useEffect(() => {
        if (initialPhotoSearchQuery !== '') {
            const unsplashPhotos = localStorage.getItem('unsplash_photos') ?? '{}';
            var parsedPhotos = JSON.parse(unsplashPhotos);
            const existingPhotosList = Object.keys(parsedPhotos).length ? parsedPhotos[form.formId] || [] : [];
            setInitialLoading(true);
            fetchPhotos(1, initialPhotoSearchQuery, false, existingPhotosList.reverse());
        }
    }, [initialPhotoSearchQuery]);

    const fetchPhotos = (page: number, text: string, reset = false, existingSelectedPhotos = []) => {
        if (isLoading || isLoadingMore) {
            return;
        }
        // the route refuses an empty or over-long query; an empty one is no search
        const query = text.trim().slice(0, MAX_QUERY_LENGTH);
        if (!query) {
            setInitialLoading(false);
            return;
        }
        if (page === 1) {
            setIsLoading(true);
        } else {
            setIsLoadingMore(true);
        }

        setPage(page);
        setSearchError(null);
        fetch(new URL('/api/unsplash', window.location.origin) + '?' + new URLSearchParams({ page: page.toString(), query }))
            .then(async (response: Response) => {
                if (!response.ok) {
                    setSearchError(searchErrorMessage(response.status));
                    return;
                }
                const feed: any = await response.json();
                const newPics = feed?.results;
                if (newPics) {
                    let mergedPics = newPics;
                    if (!reset) {
                        mergedPics = [...existingSelectedPhotos, ...pics, ...newPics];
                    }
                    setPics(mergedPics);
                    setTotal(feed.total);
                }
            })
            .catch(() => setSearchError(searchErrorMessage(0)))
            .finally(() => {
                setIsLoading(false);
                setIsLoadingMore(false);
                setInitialLoading(false);
            });
    };

    const triggerUnsplashDownloadEndpoint = (photo: any) => {
        // only the id: the route needs nothing else, and refuses large bodies
        fetch('/api/unsplash/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: photo?.id })
        }).catch(() => { });
    };

    function setPhotoInLocalStorage(photo: any) {
        const photoList = JSON.parse(localStorage.getItem('unsplash_photos') || '{}');
        const currentFormPhotoList = Object.keys(photoList).length ? photoList[form.formId] || [] : [];
        const existingPhoto = currentFormPhotoList.some((item: any) => item.id === photo.id);
        if (!existingPhoto) {
            currentFormPhotoList.push(photo);
            photoList[form.formId] = currentFormPhotoList;
            localStorage.setItem('unsplash_photos', JSON.stringify(photoList));
        }
    }

    return (
        <div className="ImagePicker border border-black-300 h-full w-full items-center rounded! bg-white">
            <div className="h-full w-full rounded-lg bg-white">
                <div className="Picker relative h-full">
                    <div className="p2-new text-black-800 flex items-center gap-4 rounded-t-lg px-4 py-[10px]">Media</div>
                    <Separator />
                    <Tabs defaultValue="upload" className="h-full w-full">
                        <TabsList className=" flex h-auto w-full gap-4 px-6 py-2">
                            <TabsTrigger value="upload">Upload</TabsTrigger>
                            <TabsTrigger value="unsplash" className="flex gap-1">
                                {/* <Link href="https://unsplash.com/?utm_source=bettercollected&utm_medium=referral" target="_blank" referrerPolicy="no-referrer" className="flex items-center gap-4 bg-white px-4 pt-4 text-lg font-bold"> */}
                                {/* <Unsplash /> */}
                                Images
                                {/* </Link> */}
                            </TabsTrigger>
                        </TabsList>
                        <Separator />
                        <TabsContent value="upload" className="px-6 pr-0! pb-4 pt-4">
                            <UploadMediaComponent updatePageImage={updatePageImage} />
                        </TabsContent>
                        <TabsContent value="unsplash" className="px-6 pr-0! pt-4">
                            <div className="mr-2 flex h-[430px] flex-col">
                                <div className="mb-6 mr-2 ">
                                    <SearchBar
                                        placeholder="Search free high-resolution images from Unsplash"
                                        className="md:w-full"
                                        initialPhotoSearchQuery={initialPhotoSearchQuery}
                                        onSearch={(query: string) => {
                                            setPics([]);
                                            fetchPhotos(1, query, true);
                                        }}
                                        query={query}
                                        setQuery={setQuery}
                                    />
                                </div>
                                {searchError && (
                                    <p role="alert" className="p4-new text-black-600 mb-4 mr-2">
                                        {searchError}
                                    </p>
                                )}
                                <PhotoList
                                    total={total}
                                    photoList={pics}
                                    isLoading={isLoading}
                                    isLoadingMore={isLoadingMore}
                                    loadMore={() => {
                                        // a failed search waits for the next one instead of retrying on every scroll
                                        if (searchError) return;
                                        query ? fetchPhotos(page + 1, query) : fetchPhotos(page + 1, 'forms');
                                    }}
                                    onPhotoSelect={async (photo: any) => {
                                        try {
                                            if (photo) {
                                                // Stored as Unsplash's address: the backend rewrites it to
                                                // its own /images/unsplash route on save when its public
                                                // address is configured, and pages always load it through
                                                // that route (utils/first-party-image.ts), never from Unsplash.
                                                updatePageImage(photo.urls.raw);
                                                setPhotoInLocalStorage(photo);
                                                triggerUnsplashDownloadEndpoint(photo);
                                                closeDialogModal();
                                            }
                                        } catch (error) {
                                            console.log(error);
                                        }
                                    }}
                                />
                            </div>
                        </TabsContent>
                    </Tabs>
                </div>
            </div>
        </div>
    );
}
