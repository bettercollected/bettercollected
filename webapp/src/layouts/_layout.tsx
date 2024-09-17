import React from 'react';

import { Box } from '@mui/material';
import cn from 'classnames';

import AuthNavbar from '@app/Components/auth/navbar';

interface LayoutProps {
    isCustomDomain?: boolean;
    isClientDomain?: boolean;
    showHamburgerIcon?: boolean;
    hideMenu?: boolean;
    className?: string;
    childClassName?: string;
    showAuthAccount?: boolean;
    hideSignIn?: boolean;
    showNavbar?: boolean;
    isFooter?: boolean;
}

export default function Layout({
    children,
    isCustomDomain = false,
    isClientDomain = false,
    hideMenu = false,
    showHamburgerIcon = false,
    className = '',
    childClassName = '',
    showNavbar = false,
    isFooter = false,
    showAuthAccount
}: React.PropsWithChildren<LayoutProps>) {
    return (
        <div className="!bg-black-200 dark:bg-dark z-20 !min-h-screen !min-w-full">
            {showNavbar && <AuthNavbar isFooter={isFooter} isCustomDomain={isCustomDomain} isClientDomain={isClientDomain} showHamburgerIcon={showHamburgerIcon} hideMenu={hideMenu} showPlans={false} showAuthAccount={showAuthAccount} />}
            <Box className={`float-none lg:float-right ${showNavbar ? ' lg:min-h-calc-68 !mt-[68px] min-h-screen ' : 'min-h-screen'} bg-black-100 w-full px-5 lg:px-10 ${className}`} component="main" sx={{ display: 'flex', width: '100%' }}>
                <div className={cn(`h-full w-full ${childClassName}`)}>{children}</div>
            </Box>
        </div>
    );
}
