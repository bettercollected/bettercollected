import React, { useEffect } from 'react';

import { useRouter } from 'next/router';

import { List, ListItem, ListItemButton, ListItemIcon, SxProps, Theme } from '@mui/material';

import { INavbarItem } from '@app/models/props/navbar';
import { isValidRelativeURL } from '@app/utils/urlUtils';


interface INavigationListProps {
    navigationList: Array<INavbarItem>;
    className?: string;
    sx?: SxProps<Theme>;
}

export default function NavigationList({ navigationList, className = '', sx = {} }: INavigationListProps) {
    const router = useRouter();

    useEffect(() => {
        navigationList?.forEach((lst) => {
            if (isValidRelativeURL(lst.url)) router.prefetch(lst.url);
        });
    }, [navigationList, router]);

    return (
        <List disablePadding sx={sx} className={className}>
            {navigationList?.map((element) => {
                const active = element.url == router.asPath;
                return (
                    <div key={element.key} className={`body4 rounded-lg mt-1 ${active ? 'bg-brand-500 !text-white' : 'text-black-600 hover:bg-brand-100'}`}>
                        <ListItem
                            disablePadding
                            onClick={() => {
                                if (element.url) {
                                    router.push(element.url, undefined, { shallow: true });
                                } else {
                                    element.onClick && element.onClick();
                                }
                            }}
                        >
                            <ListItemButton sx={{ paddingY: '8px', paddingX: '20px' }} className={`${active ? '' : 'hover:!bg-transparent'}`}>
                                {element.icon && (
                                    <ListItemIcon sx={{ minWidth: '36px' }} className={`${active ? 'text-white' : 'text-black-600'}`}>
                                        {element?.icon}
                                    </ListItemIcon>
                                )}
                                <div className="text-sm"> {element.name}</div>
                            </ListItemButton>
                        </ListItem>
                    </div>
                );
            })}
        </List>
    );
}