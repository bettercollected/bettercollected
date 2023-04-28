import React from 'react';

import { useRouter } from 'next/router';

import { List, ListItem, ListItemButton, ListItemIcon, ListItemText } from '@mui/material';

import { INavbarItem } from '@app/models/props/navbar';

interface INavigationListProps {
    navigationList: Array<INavbarItem>;
}

export default function NavigationList({ navigationList }: INavigationListProps) {
    const router = useRouter();

    return (
        <List>
            {navigationList.map((element) => {
                const Icon = element.icon;
                const active = element.url == router.asPath;
                return (
                    <ListItem key={element.key} disablePadding className={`${active ? 'bg-brand-200' : ''}`} onClick={() => router.push(element.url, undefined, { shallow: true })}>
                        <ListItemButton sx={{ paddingY: '16px', paddingX: '20px' }}>
                            {element.icon && (
                                <ListItemIcon sx={{ minWidth: '32px' }}>
                                    <Icon />
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
