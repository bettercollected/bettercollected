'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import { AppBar, IconButton, Toolbar } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import LogoApp from '@app/Components/ui/LogoApp';
import AuthAccountMenuDropdown from '@app/Components/auth/account-menu-dropdown';

export default function AuthNavbarApp({ handleDrawerToggle }: any) {

    return (
        <AppBar
            position="fixed"
            sx={{
                width: '100%',
                backgroundColor: 'white',
                color: 'black',
                boxShadow: 'none',
                borderBottom: '1px solid #E5E7EB',
                zIndex: (theme) => theme.zIndex.drawer + 1
            }}
        >
            <Toolbar className="flex justify-between px-5 lg:px-10">
                <div className="flex items-center gap-4">
                    <IconButton
                        color="inherit"
                        aria-label="open drawer"
                        edge="start"
                        onClick={handleDrawerToggle}
                        className="lg:hidden"
                    >
                        <MenuIcon />
                    </IconButton>
                    <LogoApp isCustomDomain={false} isFooter={false} isClientDomain={false} />
                </div>
                <div className="flex items-center gap-4">
                    <AuthAccountMenuDropdown hideMenu={false} isClientDomain={false} />
                </div>
            </Toolbar>
        </AppBar>
    );
}
