import React from 'react';

import { Drawer } from '@mui/material';

interface IMuiDrawerProps {
    drawerWidth?: number;
    mobileOpen?: boolean;
    handleDrawerToggle: () => void;
    anchor?: 'left' | 'top' | 'right' | 'bottom';
    mobileDrawerDisplayProps?: any;
    desktopDrawerDisplayProps?: any;
    children?: any;
}

MuiDrawer.defaultProps = {
    drawerWidth: 289,
    mobileOpen: false,
    mobileDrawerDisplayProps: { xs: 'block', sm: 'block', md: 'block', lg: 'none', xl: 'none' },
    desktopDrawerDisplayProps: { xs: 'none', sm: 'none', md: 'none', lg: 'block', xl: 'block' }
};
export default function MuiDrawer({ drawerWidth, mobileOpen, children, handleDrawerToggle, anchor = 'left', mobileDrawerDisplayProps, desktopDrawerDisplayProps }: IMuiDrawerProps) {
    const container = window !== undefined ? () => window.document.body : undefined;

    return (
        <>
            {/* Mobile drawer */}
            <Drawer
                container={container}
                variant="temporary"
                className="border-r border-r-black-200"
                open={mobileOpen}
                onClose={handleDrawerToggle}
                anchor={anchor}
                ModalProps={{
                    keepMounted: true // Better open performance on mobile.
                }}
                sx={{
                    width: drawerWidth,
                    flexShrink: 0,
                    [`& .MuiDrawer-paper`]: {
                        width: drawerWidth,
                        borderRadius: 0,
                        boxSizing: 'border-box',
                        borderWidth: '0px 1px 0px 0px',
                        borderColor: '#EEEEEE'
                    },
                    display: mobileDrawerDisplayProps
                }}
            >
                {children}
            </Drawer>

            {/* Desktop drawer */}
            <Drawer
                variant="permanent"
                className="border-r border-r-black-200"
                anchor={anchor}
                sx={{
                    width: drawerWidth,
                    flexShrink: 0,
                    [`& .MuiDrawer-paper`]: {
                        width: drawerWidth,
                        borderRadius: 0,
                        boxSizing: 'border-box',
                        borderWidth: '0px 1px 0px 0px',
                        borderColor: '#EEEEEE'
                    },
                    display: desktopDrawerDisplayProps
                }}
                open
            >
                {children}
            </Drawer>
        </>
    );
}
