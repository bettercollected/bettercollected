import React from 'react';

import { Box } from '@mui/material';
import cn from 'classnames';

import AuthNavbar from '@app/components/auth/navbar';

interface LayoutProps {
    showHamburgerIcon?: boolean;
    checkMyDataEnabled?: boolean;
    className?: string;
    hideSignIn?: boolean;
    showNavbar?: boolean;
}

export default function Layout({ children, checkMyDataEnabled = false, showHamburgerIcon = false, className = '', showNavbar = false }: React.PropsWithChildren<LayoutProps>) {
    return (
        <div className="!min-h-full !min-w-full bg-brand-100 dark:bg-dark z-20">
            {showNavbar && <AuthNavbar showHamburgerIcon={showHamburgerIcon} checkMyDataEnabled={checkMyDataEnabled} showPlans={false} />}

            <Box className={`float-none lg:float-right ${showNavbar ? 'mt-[68px] min-h-calc-68' : ''} px-5 lg:px-10 ${className}`} component="main" sx={{ display: 'flex', width: '100%' }}>
                <div className={cn('w-full h-full')}>{children}</div>
            </Box>
        </div>
    );
}
