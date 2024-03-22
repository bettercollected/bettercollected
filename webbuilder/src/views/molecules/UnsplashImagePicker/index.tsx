'use client';

import React from 'react';

import { createApi } from 'unsplash-js';

import environments from '@app/configs/environments';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FormField } from '@app/models/dtos/form';
import { Unsplash } from '@app/views/atoms/Icons/Brands/Unsplash';

import PhotoList from './PhotoList';
import SearchBar from './PhotoSearch';

interface IUnsplashImagePickerProps {
    initialPhotoSearchQuery?: string;
    onPhotoSelect?: (photo: any) => void;
    [key: string]: any;
}

export default function UnsplashImagePicker({
    initialPhotoSearchQuery = '',
    onPhotoSelect = (_: any) => {},
    ...props
}: IUnsplashImagePickerProps) {
    const [pics, setPics] = React.useState<any[]>([]);
    const [total, setTotal] = React.useState<number | undefined>();
    const [query, setQuery] = React.useState('');
    const [isLoading, setIsLoading] = React.useState(false);
    const [isLoadingMore, setIsLoadingMore] = React.useState(false);
    const [page, setPage] = React.useState(1);

    const { closeDialogModal } = useDialogModal();

    const activeSlide: FormField = props?.activeSlide;
    const updateSlideImage = props?.updateSlideImage ?? (() => {});

    const unsplash = createApi({
        accessKey: environments.NEXT_PUBLIC_UNSPLASH_ACCESS_KEY || ''
    });

    React.useEffect(() => {
        if (initialPhotoSearchQuery !== '') {
            setQuery(initialPhotoSearchQuery);
            fetchPhotos(1, initialPhotoSearchQuery);
        }
    }, []);

    const fetchPhotos = (page: number, text: string, reset = false) => {
        if (isLoading || isLoadingMore) {
            return;
        }
        if (page === 1) {
            setIsLoading(true);
        } else {
            setIsLoadingMore(true);
        }
        setPage(page);
        unsplash.search
            .getPhotos({
                page: page,
                perPage: 30,
                query: text,
                orientation: 'landscape'
            })
            .then((response: any) => {
                const newPics = response?.response?.results;
                if (newPics) {
                    let mergedPics = newPics;
                    if (!reset) {
                        mergedPics = [...pics, ...newPics];
                    }
                    setPics(mergedPics);
                    setTotal(response.response.total);
                }
                setIsLoading(false);
                setIsLoadingMore(false);
            });
    };

    return (
        <div className="ImagePicker items-center rounded bg-white">
            <div className="bg-white ">
                <div className="Picker relative h-full rounded">
                    <div className="flex items-center gap-4 bg-white px-4 pt-4 text-lg font-bold">
                        <Unsplash /> Unsplash
                    </div>
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
                            fetchPhotos(page + 1, query);
                        }}
                        onPhotoSelect={async (photo: any) => {
                            try {
                                // let blob = await fetch(photo.urls.regular).then((r) => r.blob())
                                // let image = await URL.createObjectURL(blob)
                                if (activeSlide && photo) {
                                    updateSlideImage(photo.urls.full);
                                    closeDialogModal();
                                }
                            } catch (error) {
                                console.log(error);
                            }
                        }}
                    />
                </div>
            </div>
        </div>
    );
}
