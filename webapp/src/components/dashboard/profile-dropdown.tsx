import React, { useEffect, useRef, useState } from 'react';

import Link from 'next/link';

import useOutsideClick from '@app/lib/hooks/use-outside-click';

export default function ProfileDropdown({ closeDropdown, showDropdown }: any) {
    const ref: any = useRef();

    useOutsideClick(ref, closeDropdown, showDropdown);

    return (
        <>
            <div className="absolute p-2 z-10 mt-2 w-full origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none" role="menu" aria-orientation="vertical" aria-labelledby="menu-button" tabIndex={-1} ref={ref}>
                {/* <div className={'text-gray-500 pl-3 mb-2 relative text-sm font-bold'}>Profiles</div> */}
                <div className={'overflow-y-auto'} aria-hidden>
                    <Link key={'logout'} href={`/`}>
                        <div className="p-3 cursor-pointer border-[1px] text-red-600 border-transparent hover:border-[1px] hover:border-red-600 hover:bg-red-100 hover:rounded-md" role="none">
                            Logout
                        </div>
                    </Link>
                </div>
            </div>
        </>
    );
}
