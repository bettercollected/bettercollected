import React from 'react';

import Image from 'next/image';

export default function UnsplashPhotoCard({
    photo,
    onPhotoSelect = (_: any) => {}
}: any) {
    return (
        <div
            className="theme-border-default group relative h-60 w-full cursor-pointer place-items-center border object-cover sm:h-44 md:h-32"
            key={photo.id}
            onClick={() => onPhotoSelect(photo)}
        >
            <Image
                className="card-img h-full w-full place-items-center rounded object-cover"
                src={photo.urls.thumb}
                alt={photo.alt_description}
                layout="fill"
            />
            <div
                className="invisible absolute bottom-0 left-0 right-0 top-0 group-hover:visible group-hover:bg-black/70"
                style={{ color: 'white' }}
            >
                <div className="m-2 flex place-content-center items-center justify-between space-x-1">
                    <div className="flex items-center space-x-1">
                        <Image
                            className="h-6 w-6 rounded-full"
                            src={photo.user.profile_image.small}
                            alt={photo.user.username}
                            width={24}
                            height={24}
                        />
                        <h6 className="word-breaker text-xs">{photo.user.name}</h6>
                    </div>
                </div>
            </div>
        </div>
    );
}
