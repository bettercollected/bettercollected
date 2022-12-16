import React, { useMemo } from 'react';

import Link from 'next/link';
import { useRouter } from 'next/router';

import Tooltip from '@mui/material/Tooltip';

import { authApi } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

import { HistoryIcon } from '../icons/history';
import { HomeIcon } from '../icons/home';
import { Logout } from '../icons/logout-icon';
import { SearchIcon } from '../icons/search';
import { useModal } from '../modal-views/context';

export default function Aside({ close }: { close?: () => void }) {
    const router = useRouter();

    const { openModal } = useModal();

    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select('status'), []);
    const selectGetStatus = useAppSelector(statusQuerySelect);

    const menuItems = [
        {
            href: '/mydashboard',
            title: 'Forms',
            icon: <HomeIcon className="w-[20px] h-[20px]" />
        },
        {
            href: '/mydashboard/submissions',
            title: 'Submissions',
            icon: <HistoryIcon className="w-[20px] h-[20px]" />
        },
        {
            href: '/mydashboard/settings',
            title: 'Settings',
            icon: <SearchIcon className="w-[20px] h-[20px]" />
        }
    ];

    return (
        <>
            <div className="z-10 absolute flex h-full w-full flex-grow flex-col justify-between p-5 text-primary md:relative " onTouchStart={() => {}} onTouchMove={() => {}} onTouchEnd={() => {}}>
                <div className="flex flex-col">
                    <div className={'flex items-center'}>
                        <div className=" flex  cursor-pointer items-center p-3 text-2xl font-semibold text-primary" onClick={() => {}}>
                            <div className="pl-3">
                                <div className="flex">
                                    Better<p className="text-blue-500">Collected.</p>
                                </div>
                                <div className={'text-xs font-normal text-primary opacity-70'}>Collect form responses responsibly.</div>
                            </div>
                        </div>
                    </div>

                    <div className="pt-12">
                        {menuItems.map(({ href, title, icon }) => (
                            <Link href={href} key={title}>
                                <div
                                    className={`flex items-center mb-2 ${
                                        router.asPath === href && 'text-blue-500 border-[1px] border-blue-400 rounded-md bg-blue-50 '
                                    } hover:text-blue-500 text-gray-600 cursor-pointer p-4 border-[1px] w-full border-transparent hover:border-[1px] hover:border-blue-400 hover:bg-blue-50 hover:rounded-md`}
                                    key={title}
                                >
                                    <div className="pr-2">{icon}</div>
                                    <div className="font-semibold">{title}</div>
                                </div>
                            </Link>
                        ))}
                        <div>
                            <div
                                onClick={() => openModal('LOGOUT_VIEW')}
                                className={`flex items-center text-red-600 hover:text-red-500 cursor-pointer p-4 border-[1px] w-full border-transparent hover:border-[1px] hover:border-red-400 hover:bg-red-50 hover:rounded-md`}
                                key={'logout'}
                            >
                                <div className="pr-2">
                                    <Logout height="20px" width="20px" />
                                </div>
                                <div className="font-semibold">Logout</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div>
                    <div className="mt-10 flex w-full cursor-pointer items-center justify-between rounded bg-white p-3">
                        <div className="flex w-full justify-between">
                            <div className="flex shrink flex-col justify-center pl-4">
                                <div className="flex w-full justify-between truncate">
                                    <Tooltip title={selectGetStatus?.data?.payload?.content?.user?.sub} arrow>
                                        <div className="font-bold text-md max-w-[190px] truncate">{selectGetStatus?.data?.payload?.content?.user?.sub}</div>
                                    </Tooltip>
                                </div>
                                <div className="italic text-gray-700">Free Plan</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}
