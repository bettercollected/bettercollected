import React, { ReactNode } from 'react';

import { useRouter } from 'next/router';

import { ExpandMore, SettingsOutlined } from '@mui/icons-material';
import { Accordion, AccordionDetails, AccordionSummary, Box, Divider, Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Toolbar } from '@mui/material';

import { DashboardIcon } from '@app/components/icons/dashboard-icon';
import { FormIcon } from '@app/components/icons/form-icon';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetAllMineWorkspacesQuery } from '@app/store/workspaces/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

import AuthAccountProfileImage from '../auth/account-profile-image';

interface INavbarList {
    key: string;
    name: string;
    url: string;
    icon: any;
}

interface IMuiDrawerProps {
    drawerWidth?: number;
    mobileOpen?: boolean;
    handleDrawerToggle: () => void;
    drawer: ReactNode;
    anchor?: 'left' | 'top' | 'right' | 'bottom';
    mobileDrawerDisplayProps?: any;
    desktopDrawerDisplayProps?: any;
}

MuiDrawer.defaultProps = {
    drawerWidth: 289,
    mobileOpen: false,
    mobileDrawerDisplayProps: { xs: 'block', sm: 'block', md: 'block', lg: 'none', xl: 'none' },
    desktopDrawerDisplayProps: { xs: 'none', sm: 'none', md: 'none', lg: 'block', xl: 'block' }
};
export default function MuiDrawer({ drawerWidth, mobileOpen, drawer, handleDrawerToggle, anchor = 'left', mobileDrawerDisplayProps, desktopDrawerDisplayProps }: IMuiDrawerProps) {
    const container = window !== undefined ? () => window.document.body : undefined;

    return (
        <>
            {/* Mobile drawer */}
            <Drawer
                container={container}
                variant="temporary"
                open={mobileOpen}
                onClose={handleDrawerToggle}
                anchor={anchor}
                ModalProps={{
                    keepMounted: true // Better open performance on mobile.
                }}
                sx={{
                    width: drawerWidth,
                    flexShrink: 0,
                    [`& .MuiDrawer-paper`]: { width: drawerWidth, borderRadius: 0, boxSizing: 'border-box' },
                    display: mobileDrawerDisplayProps
                }}
            >
                {drawer}
            </Drawer>

            {/* Desktop drawer */}
            <Drawer
                variant="permanent"
                anchor={anchor}
                sx={{
                    width: drawerWidth,
                    flexShrink: 0,
                    [`& .MuiDrawer-paper`]: { width: drawerWidth, borderRadius: 0, boxSizing: 'border-box' },
                    display: desktopDrawerDisplayProps
                }}
                open
            >
                {drawer}
            </Drawer>
        </>
    );
}
