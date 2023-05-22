import React from 'react';

import { Box } from '@mui/material';
import cn from 'classnames';

import AuthNavbar from '@app/components/auth/navbar';

interface LayoutProps {
    isCustomDomain?: boolean;
    isClientDomain?: boolean;
    showHamburgerIcon?: boolean;
    hideMenu?: boolean;
    className?: string;
    showAuthAccount?: boolean;
    hideSignIn?: boolean;
    showNavbar?: boolean;
}

export default function Layout({ children, isCustomDomain = false, isClientDomain = false, hideMenu = false, showHamburgerIcon = false, className = '', showNavbar = false, showAuthAccount }: React.PropsWithChildren<LayoutProps>) {
    return (
        <div className="!min-h-screen !min-w-full bg-brand-100 dark:bg-dark z-20">
            {showNavbar && <AuthNavbar isCustomDomain={isCustomDomain} isClientDomain={isClientDomain} showHamburgerIcon={showHamburgerIcon} hideMenu={hideMenu} showPlans={false} showAuthAccount={showAuthAccount} />}

            <Box className={`float-none lg:float-right ${showNavbar ? 'mt-[68px] min-h-calc-68' : 'min-h-screen'} px-5 lg:px-10 ${className}`} component="main" sx={{ display: 'flex', width: '100%' }}>
                <div className={cn('w-full h-full')}>{children}</div>
            </Box>
        </div>
    );
}
