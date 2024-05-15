'use client';

import React from 'react';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { Unsplash } from '@app/views/atoms/Icons/Brands/Unsplash';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import CircularProgressBar from '@app/views/atoms/Loaders/CircularLoadingAnimation';
import PhotoList from './PhotoList';
import SearchBar from './PhotoSearch';
import Link from 'next/link';

interface IUnsplashImagePickerProps {
    initialPhotoSearchQuery?: string;
    onPhotoSelect?: (photo: any) => void;

    [key: string]: any;
}

export default function UnsplashImagePicker({ initialPhotoSearchQuery = '', onPhotoSelect = (_: any) => {}, ...props }: IUnsplashImagePickerProps) {
    const [pics, setPics] = React.useState<any[]>([]);
    const [total, setTotal] = React.useState<number | undefined>();
    const [query, setQuery] = React.useState('');
    const [isLoading, setIsLoading] = React.useState(false);
    const [initialLoading, setInitialLoading] = React.useState(false);
    const [isLoadingMore, setIsLoadingMore] = React.useState(false);
    const [page, setPage] = React.useState(1);
    const form = useAppSelector(selectForm);

    const { closeDialogModal } = useDialogModal();

    const updatePageImage = props?.updatePageImage ?? (() => {});

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
        if (page === 1) {
            setIsLoading(true);
        } else {
            setIsLoadingMore(true);
        }

        setPage(page);
        fetch(new URL('/api/unsplash', window.location.origin) + '?' + new URLSearchParams({ page: page.toString(), query: text })).then((response: any) => {
            response.json().then((response: any) => {
                const newPics = response?.results;
                if (newPics) {
                    let mergedPics = newPics;
                    if (!reset) {
                        mergedPics = [...existingSelectedPhotos, ...pics, ...newPics];
                    }
                    setPics(mergedPics);
                    setTotal(response.total);
                }
                setIsLoading(false);
                setIsLoadingMore(false);
                setInitialLoading(false);
            });
        });
    };

    const triggerUnsplashDownloadEndpoint = (photo: any) => {
        fetch('/api/unsplash/download', {
            method: 'POST',
            body: JSON.stringify(photo)
        });
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
        <div className="ImagePicker items-center  rounded bg-white">
            {initialLoading ? (
                <div className="flex h-full w-full justify-center">
                    <CircularProgressBar className="h-10 w-10" />
                </div>
            ) : (
                <div className="bg-white ">
                    <div className="Picker relative h-full rounded">
                        <Link href="https://unsplash.com/?utm_source=bettercollected&utm_medium=referral" target="_blank" referrerPolicy="no-referrer" className="flex items-center gap-4 bg-white px-4 pt-4 text-lg font-bold">
                            <Unsplash /> Unsplash
                        </Link>
                        <div className="bg-white p-4 shadow">
                            <SearchBar
                                onSearch={(query: string) => {
                                    setPics([]);
                                    fetchPhotos(1, query, true);
                                }}
                                query={query}
                                setQuery={setQuery}
                            />
                        </div>

                        <PhotoList
                            total={total}
                            photoList={pics}
                            isLoading={isLoading}
                            isLoadingMore={isLoadingMore}
                            loadMore={() => {
                                query ? fetchPhotos(page + 1, query) : fetchPhotos(page + 1, 'forms');
                            }}
                            onPhotoSelect={async (photo: any) => {
                                try {
                                    if (photo) {
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
                </div>
            )}
        </div>
    );
}
