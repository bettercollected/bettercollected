import React from 'react';

import Image from 'next/image';
import Link from 'next/link';

export default function UnsplashPhotoCard({ photo, onPhotoSelect = (_: any) => {} }: any) {
    return (
        <div className="theme-border-default group relative h-60 w-full cursor-pointer place-items-center border object-cover sm:h-44 md:h-32" key={photo.id} onClick={() => onPhotoSelect(photo)}>
            <Image className="card-img h-full w-full place-items-center rounded object-cover" src={photo.urls.thumb} alt={photo.alt_description} fill sizes="(min-width 100px) 100%" />
            <div className="invisible absolute bottom-0 left-0 right-0 top-0 group-hover:visible group-hover:bg-black/70" style={{ color: 'white' }}>
                <div className="m-2 flex place-content-center items-center justify-between space-x-1">
                    <Link href={photo.user.links.html + '?utm_source=bettercollected&utm_medium=referral'} target="_blank" referrerPolicy="no-referrer" className="flex items-center space-x-1">
                        <Image className="h-6 w-6 rounded-full" src={photo.user.profile_image.small} alt={photo.user.username} width={24} height={24} />
                        <h6 className="word-breaker text-xs hover:underline">{photo.user.name}</h6>
                    </Link>
                </div>
            </div>
        </div>
    );
}
