import React, { useState } from 'react';

import Image from 'next/image';
import Link from 'next/link';
import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import { cn } from '@app/shadcn/util/lib';

export default function UnsplashPhotoCard({ photo, onPhotoSelect = (_: any) => {} }: any) {
    return (
        <div className="theme-border-default group relative h-auto w-full cursor-pointer place-items-center rounded border" key={photo.id} onClick={() => onPhotoSelect(photo)}>
            <ImageWithLoader photo={photo} />
            {/* <Image style={{ objectFit: 'cover', width: '100%', height: 'auto' }} className="card-img place-items-center rounded " src={photo.urls.full} sizes="10vw" alt={photo.alt_description} width={0} height={0} /> */}
            <div className="invisible absolute inset-0 h-full rounded group-hover:visible group-hover:bg-black/60" style={{ color: 'white' }}>
                <div className="flex place-content-center items-center justify-between space-x-1 p-4">
                    <Link
                        href={photo.user.links.html + '?utm_source=bettercollected&utm_medium=referral'}
                        target="_blank"
                        referrerPolicy="no-referrer"
                        className="flex items-center space-x-1"
                        onClick={(e: any) => {
                            e.stopPropagation();
                        }}
                    >
                        <Image className="h-6 w-6 rounded-full" src={photo.user.profile_image.small} alt={photo.user.username} width={24} height={24} />
                        <h6 className="word-breaker text-xs hover:underline">{photo.user.name}</h6>
                    </Link>
                </div>
            </div>
        </div>
    );
}

const ImageWithLoader = ({ photo }: { photo: any }) => {
    const [nextImageLoading, setNextImageLoading] = useState(true);

    return (
        <div className={cn(`h-full w-full`)}>
            <Image
                style={{ objectFit: 'cover', width: '100%', height: 'auto' }}
                className="card-img place-items-center rounded "
                onLoadingComplete={() => {
                    setNextImageLoading(false);
                }}
                src={photo.urls.full}
                sizes="10vw"
                alt={photo.alt_description}
                width={0}
                height={0}
            />
            {nextImageLoading && <Skeleton className=" bg-black-300 z-[10] h-[200px] w-full" />}
        </div>
    );
};
