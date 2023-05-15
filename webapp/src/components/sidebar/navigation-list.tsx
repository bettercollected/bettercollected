import React from 'react';

import { useRouter } from 'next/router';

import { List, ListItem, ListItemButton, ListItemIcon, ListItemText, SxProps, Theme } from '@mui/material';

import { INavbarItem } from '@app/models/props/navbar';

interface INavigationListProps {
    navigationList: Array<INavbarItem>;
    className?: string;
    sx?: SxProps<Theme>;
}

export default function NavigationList({ navigationList, className = '', sx = {} }: INavigationListProps) {
    const router = useRouter();

    return (
        <List disablePadding sx={sx} className={className}>
            {navigationList.map((element) => {
                const active = element.url == router.asPath;
                return (
                    <ListItem key={element.key} disablePadding className={`${active ? 'bg-brand-200 text-brand-600' : ''}`} onClick={() => router.push(element.url, undefined, { shallow: true })}>
                        <ListItemButton sx={{ paddingY: '16px', paddingX: '20px' }} className={`${active ? '' : 'hover:bg-brand-100'}`}>
                            {element.icon && (
                                <ListItemIcon sx={{ minWidth: '32px' }} className={`${active ? 'text-brand-600' : 'text-black-900'}`}>
                                    {element?.icon}
                                </ListItemIcon>
                            )}
                            <ListItemText primary={element.name} />
                        </ListItemButton>
                    </ListItem>
                );
            })}
        </List>
    );
}
